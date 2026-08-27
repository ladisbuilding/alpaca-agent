"""The committee cycle — one full pass from market snapshot to decision record.

    snapshot -> scouts nominate -> deterministic build -> PRE-GATE
             -> bull / bear debate -> risk officer -> FINAL GATE -> executor
             -> decision record

Two ordering decisions are load-bearing:

1. **The gates run BEFORE the debate.** A structure the deterministic layer has already
   rejected is not worth $3 of argument. Checking the cheap thing first is both correct and
   economical, and the record still shows exactly why it was refused.

2. **Everything is built and argued from ONE snapshot.** The first live Bear turn caught its
   input being stale and argued about a trade that no longer existed. Passing a single
   immutable snapshot through the whole cycle is what prevents that.

A cycle that places no trade is a normal, frequent, successful outcome. The decision record
for a refusal is as complete as the record for a fill — "why we didn't" is the more
interesting half of an autonomous trader's log, and it is what the dashboard leads with.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime
from typing import Any, Sequence

from anthropic import AsyncAnthropic

from .chain import LiquidityFilter, expiries_within
from .gates import GateResult, Proposal, Right, RiskConfig, evaluate, summarize
from .llm import Turn, run_turn
from .manage import ExitDecision, ManageConfig, held_positions, review
from .market import MarketSnapshot
from .mcp_client import McpCredentials, scoped_session
from .roles import (
    BEAR,
    BULL,
    EXECUTOR,
    PORTFOLIO_MANAGER,
    RISK_OFFICER,
    SCOUT_DIRECTIONAL,
    SCOUT_PREMIUM,
    Role,
)
from .regime import Regime
from .screener import Candidate, buyable, sellable
from .switches import Switches
from .strategy import (
    CalendarConfig,
    size_for_risk,
    DirectionalConfig,
    IncomeConfig,
    build_calendar,
    build_credit_vertical,
    build_debit_vertical,
    build_iron_condor,
)

PRICES = {"claude-opus-5": (5.0, 25.0), "claude-sonnet-5": (3.0, 15.0)}


@dataclass
class Nomination:
    underlying: str
    sleeve: str  # "income" | "directional"
    direction: str | None  # "bullish" | "bearish" | None
    reason: str
    conviction: int
    source: str  # which scout


@dataclass
class Deliberation:
    """One structure's full journey through the committee."""

    nomination: Nomination
    strategy: str
    structure: dict[str, Any]
    pre_gate: dict[str, Any]
    debated: bool = False
    bull: str | None = None
    bear: str | None = None
    bear_verdict: str | None = None
    risk_officer: str | None = None
    pm_decision: str | None = None
    final_gate: dict[str, Any] | None = None
    executed: bool = False
    execution_note: str | None = None
    evidence: list[str] = field(default_factory=list)


@dataclass
class CycleRecord:
    """The artifact. Written to disk, served by the api, rendered by the dashboard, and
    mined for the daily post."""

    started_at: str
    finished_at: str | None = None
    dry_run: bool = True
    market_open: bool = False
    equity: float = 0.0
    open_positions: int = 0
    universe: list[str] = field(default_factory=list)
    nominations: list[dict[str, Any]] = field(default_factory=list)
    deliberations: list[dict[str, Any]] = field(default_factory=list)
    turns: list[dict[str, Any]] = field(default_factory=list)
    # ⚠️ ORDERS placed, not trades done. A multi-leg limit order can rest unfilled all day:
    # the first live run reported "2 trades placed" while the broker showed zero positions
    # and zero fills. Conflating submission with execution is exactly how a bot once
    # reported $2,015 on a book that had made $89. Fills are established by the Auditor
    # from broker activity, never inferred from our own order log.
    orders_placed: int = 0
    positions_closed: int = 0
    exits: list[dict[str, Any]] = field(default_factory=list)
    cost_usd: float = 0.0
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str)


def _record_turn(record: CycleRecord, turn: Turn) -> None:
    prices = PRICES.get(turn.model, (5.0, 25.0))
    record.cost_usd += turn.cost_usd(*prices)
    record.turns.append(
        {
            "role": turn.role,
            "model": turn.model,
            "text": turn.text,
            "tool_calls": len(turn.tool_calls),
            "evidence": turn.evidence,
            "refused": turn.refused,
            "error": turn.error,
            "input_tokens": turn.input_tokens,
            "output_tokens": turn.output_tokens,
            "cache_read_tokens": turn.cache_read_tokens,
        }
    )


def _gate_dict(result: GateResult) -> dict[str, Any]:
    return {
        "approved": result.approved,
        "blocked_by": result.blocked_by,
        "reasons": result.reasons,
        "warnings": result.warnings,
        "summary": summarize(result),
    }


def _structure_dict(p: Proposal) -> dict[str, Any]:
    return {
        "underlying": p.underlying,
        "strategy": p.strategy,
        "expiry": p.expiry.isoformat(),
        "legs": [
            {
                "symbol": l.symbol,
                "side": l.side.value,
                "qty": l.qty,
                "right": l.right.value,
                "strike": l.strike,
            }
            for l in p.legs
        ],
        "net_credit": round(p.net_credit, 2),
        "max_loss": round(p.max_loss, 2),
        "max_profit": round(p.max_profit, 2),
        "bid_ask_pct": round(p.bid_ask_pct, 4),
        "fingerprint": p.fingerprint,
    }


def read_verdict(text: str, *, default: str = "ALLOW") -> str:
    """Extract the Bear's verdict from its reply.

    A naive `"KILL" in text` inverted a real decision: the Bear wrote *"It's symmetric, not
    adverse, so not a kill"* — recommending ALLOW — and the committee's TAKE was recorded as
    a refusal. The word appeared inside a sentence saying the opposite.

    The prompt asks for the verdict at the END, so the LAST standalone occurrence wins, and
    an occurrence negated by a preceding "not" is ignored.
    """
    upper = text.upper()
    last: tuple[int, str] | None = None
    for word in ("KILL", "ALLOW"):
        start = 0
        while True:
            i = upper.find(word, start)
            if i == -1:
                break
            start = i + 1
            # Skip a negated mention: "not a kill", "not kill", "rather than kill".
            preceding = upper[max(0, i - 24) : i]
            if "NOT " in preceding or "RATHER THAN " in preceding or "N'T " in preceding:
                continue
            # Skip mentions inside a longer word (KILLED, ALLOWANCE, ALLOWED).
            after = upper[i + len(word) : i + len(word) + 2]
            if after[:1].isalpha():
                continue
            if last is None or i > last[0]:
                last = (i, word)
    return last[1] if last else default


def parse_nominations(
    text: str, source: str, default_sleeve: str, universe: Sequence[str] | None = None
) -> list[Nomination]:
    """Pull nominations out of a scout's reply.

    Scouts write prose, so this is tolerant by design: a scout that returns nothing usable
    yields no nominations, which is a valid and common outcome rather than an error. Being
    strict here would turn a chatty reply into a crashed cycle.

    Two things make it tolerant WITHOUT being credulous:

    * **Nominations must be in the universe.** Scouts are told to nominate from the universe
      only, so anything outside it is a parse artifact. Without this, a scout's caveat line
      "Note: both expiries are 0-1 DTE..." became a nomination for a ticker called NOTE.
    * **One nomination per (underlying, sleeve).** A scout that argues in prose and then
      restates its pick as a summary line would otherwise be counted twice, which inflates
      the nomination count and sends the same structure through the gates repeatedly.
    """
    # A scout that declines must be taken at its word. One that wrote "No nominations." and
    # then EXPLAINED why — "QQQ IV/RV 1.05x is cheap (not rich)..." — had a QQQ nomination
    # parsed straight out of its reasoning, because the ticker is in the universe and the
    # line looked like every other line. An explicit refusal outranks the line scanner.
    first_line = next((l.strip().lower() for l in text.splitlines() if l.strip()), "")
    if any(
        phrase in first_line
        for phrase in ("no nomination", "none qualify", "nothing qualifies", "standing down", "no candidates")
    ):
        return []

    allowed = {u.upper() for u in universe} if universe else None
    seen: set[tuple[str, str]] = set()
    out: list[Nomination] = []
    for raw in text.splitlines():
        line = raw.strip().lstrip("-*0123456789. ").strip()
        if not line or len(line) < 4:
            continue
        head = line.split()[0].strip("*:,()").upper()
        if not (1 <= len(head) <= 5 and head.isalpha()):
            continue
        if allowed is not None and head not in allowed:
            continue
        if head in {"NONE", "NO", "I", "THE", "A", "AN", "IF", "IT", "AT", "AS", "TO", "NOTE"}:
            continue
        lowered = line.lower()
        direction = "bearish" if "bearish" in lowered else ("bullish" if "bullish" in lowered else None)
        # Read the stated conviction. Tokens carry punctuation ("conviction 5." / "4/5"),
        # so strip it before testing — a bare isdigit() check silently defaulted every
        # nomination to 3, which flattened the ordering that decides what gets debated.
        conviction = 3
        m = re.search(r"conviction\D{0,3}([1-5])", line, re.IGNORECASE)
        if m:
            conviction = int(m.group(1))
        else:
            for token in line.replace("/", " ").split():
                stripped = token.strip(".,;:()[]*")
                if stripped.isdigit() and 1 <= int(stripped) <= 5:
                    conviction = int(stripped)
                    break
        if (head, default_sleeve) in seen:
            continue
        seen.add((head, default_sleeve))
        out.append(
            Nomination(
                underlying=head,
                sleeve=default_sleeve,
                direction=direction,
                reason=line[:300],
                conviction=conviction,
                source=source,
            )
        )
    return out[:3]


def build_for(
    nom: Nomination,
    snapshot: MarketSnapshot,
    income: IncomeConfig,
    directional: DirectionalConfig,
    risk_budget: float = 0.0,
) -> Proposal | None:
    """Deterministic construction. The scout chose the symbol and the stance; every strike
    below comes from code reading the live chain."""
    chain = snapshot.chain(nom.underlying)
    if not chain:
        return None
    liquidity = LiquidityFilter()
    cfg = income if nom.sleeve == "income" else directional
    if nom.sleeve == "long_premium" and nom.direction is None:
        cfg = directional  # placeholder; the calendar branch picks its own expiries
    expiries = expiries_within(chain, snapshot.today, cfg.min_dte, cfg.max_dte)
    if not expiries:
        return None
    expiry = expiries[0]

    def sized(builder):
        """Scale to the risk budget; the gates remain the ceiling."""
        if risk_budget <= 0:
            return builder(income.qty)
        return size_for_risk(builder, risk_budget)

    if nom.sleeve == "income":
        if nom.direction == "bullish":
            return sized(lambda q: build_credit_vertical(
                chain, expiry, Right.PUT, replace(income, qty=q), liquidity))
        if nom.direction == "bearish":
            return sized(lambda q: build_credit_vertical(
                chain, expiry, Right.CALL, replace(income, qty=q), liquidity))
        return sized(lambda q: build_iron_condor(chain, expiry, replace(income, qty=q), liquidity))

    if nom.sleeve == "long_premium":
        # Directionless view in a cheap-premium regime → calendar. With a direction, a debit
        # vertical expresses it more cleanly than a calendar does.
        if nom.direction is None:
            cal = CalendarConfig()
            nears = expiries_within(chain, snapshot.today, cal.near_min_dte, cal.near_max_dte)
            fars = expiries_within(chain, snapshot.today, cal.near_min_dte + cal.far_min_gap, 60)
            for near in nears:
                far = next((f for f in fars if (f - near).days >= cal.far_min_gap), None)
                if far:
                    built = build_calendar(chain, near, far, Right.CALL, cal, liquidity)
                    if built:
                        return built
            return None
        right = Right.PUT if nom.direction == "bearish" else Right.CALL
        return sized(lambda q: build_debit_vertical(
            chain, expiry, right, replace(directional, qty=q), liquidity))

    right = Right.PUT if nom.direction == "bearish" else Right.CALL
    return build_debit_vertical(chain, expiry, right, directional, liquidity)


async def _scout(
    client: AsyncAnthropic,
    role: Role,
    creds: McpCredentials,
    snapshot: MarketSnapshot,
    universe: list[str],
    record: CycleRecord,
    sleeve: str,
    candidates: list[Candidate] | None = None,
) -> list[Nomination]:
    # ⚠️ Nominations are validated against this list. It must include the SCREENED candidates,
    # not just the seed universe — the ticker filter exists to reject parse artifacts (a
    # caveat line once became a ticker called NOTE), and validating against the seeds alone
    # turns it into a second, invisible universe cap.
    #
    # It cost us the best setup of the week: the directional scout nominated NVDA on a
    # +9% post-earnings catalyst, with price-target hikes cited and conviction correctly
    # sized down — and the parser discarded it because NVDA was not one of my three seeds.
    allowed = list(dict.fromkeys(list(universe) + [c.symbol for c in (candidates or [])]))
    context = "\n".join(snapshot.describe(u) for u in universe)
    reads = [snapshot.regime(u) for u in universe]
    verdicts = "\n".join(f"  {r.explain()}" for r in reads)
    # Whether the strategy's premise holds today is arithmetic, not a matter of opinion —
    # so the scouts are told the answer rather than asked to derive it.
    sellable = [r.underlying for r in reads if r.regime is Regime.PREMIUM_RICH]
    buyable = [r.underlying for r in reads if r.regime is Regime.PREMIUM_CHEAP]
    prompt = (
        f"Snapshot taken {snapshot.taken_at:%Y-%m-%d %H:%M} UTC. Market "
        f"{'OPEN' if snapshot.is_open else 'CLOSED'}.\n"
        f"Equity ${snapshot.portfolio.equity:,.0f}, "
        f"{len(snapshot.portfolio.open_positions)} open position(s).\n\n"
        f"Universe:\n{context}\n\n"
        f"Volatility regime (measured deterministically — do not re-derive these):\n{verdicts}\n\n"
        + (
            f"Premium is RICH on: {', '.join(sellable)}. Selling defined-risk premium is "
            "justified there.\n"
            if sellable
            else "Premium is rich NOWHERE today — selling it is not paid for.\n"
        )
        + (
            f"Premium is CHEAP on: {', '.join(buyable)}. Buying premium (debit verticals, "
            "calendars) is the appropriate expression there.\n"
            if buyable
            else ""
        )
        + (
            "\nSCREENED CANDIDATES — measured across the most active and most-moved names, "
            "filtered to those whose option chains are actually tradeable, ranked by edge:\n"
            + "\n".join(f"  {c.describe()}" for c in (candidates or [])[:8])
            + "\n"
            if candidates
            else ""
        )
        + (
            "\nYou also have get_news, get_market_movers and get_most_active_stocks. Use them "
            "when a catalyst would change your read — a name that has already moved on news "
            "prices differently from one that has not.\n"
            if sleeve == "directional"
            else ""
        )
        + "\nNominate from the universe or the screened candidates, and only where the regime "
        "supports your sleeve. "
        "One nomination per line, starting with the ticker. Returning nothing is correct and "
        "common — a regime with no edge deserves no nominations."
    )
    try:
        async with scoped_session(role.toolsets, creds) as (session, schemas):
            turn = await run_turn(client, role, session, schemas, prompt)
    except Exception as exc:  # noqa: BLE001 — an MCP server that fails to start, etc.
        record.notes.append(f"{role.name} unavailable: {type(exc).__name__}: {exc}")
        return []
    _record_turn(record, turn)
    if turn.error:
        record.notes.append(f"{role.name} errored: {turn.error}")
        return []
    return parse_nominations(turn.text, role.name, sleeve, allowed)


async def run_cycle(
    snapshot: MarketSnapshot,
    creds: McpCredentials,
    anthropic_key: str,
    *,
    universe: list[str],
    risk: RiskConfig | None = None,
    income: IncomeConfig | None = None,
    directional: DirectionalConfig | None = None,
    dry_run: bool = True,
    kill_switch: bool = False,
    recent_fingerprints: list[tuple[str, date]] | None = None,
    max_trades: int = 2,
    rehearse: bool = False,
    max_cycle_usd: float = 6.0,
    open_decisions: list[dict[str, Any]] | None = None,
    broker_positions: list[dict[str, Any]] | None = None,
    manage_config: ManageConfig | None = None,
    switches: Switches | None = None,
    candidates: list[Candidate] | None = None,
) -> CycleRecord:
    """`max_cycle_usd` stops a single sitting that turns pathological. An observed debating
    cycle costs ~$2; the structural worst case is ~$11. This runs unattended, so it must be
    able to stand itself down rather than wait to be noticed.

    `rehearse` tells the gates the market is open even when it is not, purely to
    exercise the debate path end to end. Quotes are stale, so the CONCLUSIONS are
    meaningless — the point is proving the plumbing before it runs unattended. Rehearsals
    force dry_run and are marked in the record so they can never be mistaken for a sitting
    that mattered."""
    risk = risk or RiskConfig()
    income = income or IncomeConfig()
    directional = directional or DirectionalConfig()
    recent = recent_fingerprints or []
    switches = switches or Switches()
    now = datetime.now().astimezone()

    if rehearse:
        dry_run = True
        # A rehearsal has to pretend it is mid-session as well as pretending the market is
        # open, or NEAR_CLOSE blocks everything the moment you run it in the evening —
        # which is exactly when you would be rehearsing.
        now = now.replace(hour=11, minute=0, second=0, microsecond=0)

    record = CycleRecord(
        started_at=snapshot.taken_at.isoformat(),
        dry_run=dry_run,
        market_open=snapshot.is_open,
        equity=snapshot.portfolio.equity,
        open_positions=len(snapshot.portfolio.open_positions),
        universe=universe,
    )
    gates_see_open = snapshot.is_open or rehearse
    if not switches.all_active:
        record.notes.append(f"Strategy switches: {switches.describe()}")
    if rehearse:
        record.notes.append(
            "REHEARSAL — gates told the market is open to exercise the debate path. "
            "Quotes are stale; conclusions here mean nothing. Plumbing only."
        )
    client = AsyncAnthropic(api_key=anthropic_key)

    # ── 0. Manage what we already hold, BEFORE looking for anything new ───────────
    # Freeing risk and buying power matters more than adding to the book, and an exit is
    # deterministic — it costs nothing and should never wait behind a debate.
    held = held_positions(broker_positions or [], open_decisions or [])
    exits: list[ExitDecision] = review(
        held, snapshot.today, manage_config,
        spots={k: v for k, v in snapshot.spot.items()},
        kill_switch=kill_switch,
        switches=switches,
    )
    for decision in exits:
        record.exits.append(
            {
                "underlying": decision.position.underlying,
                "strategy": decision.position.strategy,
                "fingerprint": decision.position.fingerprint,
                "reason": decision.reason.value,
                "detail": decision.detail,
                "unrealized": round(decision.position.unrealized, 2),
                "closed": False,
            }
        )
    if held:
        record.notes.append(
            f"Managing {len(held)} open position(s); {len(exits)} flagged for exit."
        )

    if exits and not dry_run:
        async with scoped_session(EXECUTOR.toolsets, creds) as (session, schemas):
            for i, decision in enumerate(exits):
                p = decision.position
                turn = await run_turn(
                    client, EXECUTOR, session, schemas,
                    "CLOSE this position. Place the closing multi-leg order via "
                    "place_option_order — buy back what we sold and sell what we bought.\n\n"
                    f"Underlying {p.underlying}, {p.strategy}, expiry {p.expiry}.\n"
                    f"Reason: {decision.reason.value} — {decision.detail}\n"
                    "Use get_all_positions to read the exact legs and quantities first.",
                )
                _record_turn(record, turn)
                closed = any(
                    c.tool == "place_option_order" and not c.result.startswith(("ERROR", "DENIED"))
                    for c in turn.tool_calls
                )
                record.exits[i]["closed"] = closed
                record.exits[i]["note"] = turn.text[:400]
                if closed:
                    record.positions_closed += 1
    elif exits:
        for e in record.exits:
            e["note"] = "DRY RUN — flagged for exit but not sent to the broker."

    # ── 1. Scouts nominate (concurrently — they are independent by design) ─────────
    premium, direction = await asyncio.gather(
        _scout(client, SCOUT_PREMIUM, creds, snapshot, universe, record, "income",
               candidates=candidates),
        _scout(client, SCOUT_DIRECTIONAL, creds, snapshot, universe, record, "directional",
               candidates=candidates),
    )
    # ⚠️ Directional trades require a CATALYST, not a narrative. Every losing trade so far was
    # a story ("QQQ fell 6 of 7 sessions") that the Bear dismantled; the premium sleeve, which
    # trades a measured edge, is the one that made money. A resolved binary or a >3% day move
    # is a checkable input — a chart description is not.
    catalyst_names = {c.symbol.upper() for c in (candidates or []) if c.event_flagged or (c.day_move is not None and abs(c.day_move) >= 0.03)}
    if candidates:
        before = len(direction)
        direction = [n for n in direction if n.underlying.upper() in catalyst_names]
        if before != len(direction):
            record.notes.append(
                f"Dropped {before - len(direction)} directional nomination(s) with no catalyst. "
                f"Catalysts today: {', '.join(sorted(catalyst_names)) or 'none'}."
            )

    nominations = premium + direction
    nominations.sort(key=lambda n: -n.conviction)
    record.nominations = [asdict(n) for n in nominations]
    if not nominations:
        record.notes.append("No nominations. A quiet cycle is a legitimate outcome.")
        record.finished_at = datetime.now().astimezone().isoformat()
        return record

    # ── 2. Deterministic build + PRE-GATE, before spending money on debate ─────────
    deliberations: list[Deliberation] = []
    built: list[tuple[Deliberation, Proposal]] = []  # carried forward, never rebuilt
    for nom in nominations:
        proposal = build_for(
            nom, snapshot, income, directional,
            risk_budget=snapshot.portfolio.equity * risk.max_loss_per_trade_pct * 0.80,
        )
        if proposal is None:
            deliberations.append(
                Deliberation(
                    nomination=nom,
                    strategy="none",
                    structure={},
                    pre_gate={"approved": False, "blocked_by": ["NO_STRUCTURE"],
                              "reasons": [f"No sound structure available on {nom.underlying}."],
                              "warnings": [], "summary": "BLOCKED by NO_STRUCTURE"},
                )
            )
            continue
        gate = evaluate(
            proposal, snapshot.portfolio, risk, now,
            kill_switch=kill_switch, market_open=gates_see_open,
            recent_fingerprints=recent,
            switch_reason=switches.block_reason(proposal.strategy),
        )
        deliberation = Deliberation(
            nomination=nom,
            strategy=proposal.strategy,
            structure=_structure_dict(proposal),
            pre_gate=_gate_dict(gate),
        )
        deliberations.append(deliberation)
        built.append((deliberation, proposal))

    # Debate only what the deterministic layer already cleared, highest conviction first.
    survivors = [(d, p) for d, p in built if d.pre_gate["approved"]][:max_trades]

    if not survivors:
        record.notes.append(
            "Every candidate was refused by the deterministic gates before debate — "
            "no model tokens spent arguing about structures that could not be taken."
        )

    # ── 3. Debate the survivors ───────────────────────────────────────────────────
    for deliberation, proposal in survivors:
        if record.cost_usd >= max_cycle_usd:
            record.notes.append(
                f"Spend ceiling reached (${record.cost_usd:.2f} of ${max_cycle_usd:.2f}). "
                "Remaining candidates were not debated. A sitting that costs this much is "
                "misbehaving, not working hard."
            )
            break
        deliberation.debated = True
        brief = (
            f"Snapshot {snapshot.taken_at:%Y-%m-%d %H:%M} UTC "
            f"(all figures below come from this one snapshot).\n"
            f"Nominated by {deliberation.nomination.source}: {deliberation.nomination.reason}\n\n"
            f"Structure: {json.dumps(deliberation.structure, indent=2)}\n\n"
            f"Book: equity ${snapshot.portfolio.equity:,.0f}, "
            f"{len(snapshot.portfolio.open_positions)} open position(s), "
            f"${snapshot.portfolio.deployed_risk:,.0f} risk deployed.\n"
            f"Deterministic gates: {deliberation.pre_gate['summary']}"
        )

        async with scoped_session(BULL.toolsets, creds) as (session, schemas):
            bull_turn = await run_turn(client, BULL, session, schemas, brief)
        _record_turn(record, bull_turn)
        deliberation.bull = bull_turn.text
        deliberation.evidence += bull_turn.evidence

        async with scoped_session(BEAR.toolsets, creds) as (session, schemas):
            bear_turn = await run_turn(
                client, BEAR, session, schemas,
                brief + f"\n\nThe Bull argues:\n{bull_turn.text}",
            )
        _record_turn(record, bear_turn)
        deliberation.bear = bear_turn.text
        deliberation.bear_verdict = read_verdict(bear_turn.text)
        deliberation.evidence += bear_turn.evidence

        async with scoped_session(RISK_OFFICER.toolsets, creds) as (session, schemas):
            ro_turn = await run_turn(
                client, RISK_OFFICER, session, schemas,
                brief + f"\n\nBull:\n{bull_turn.text}\n\nBear:\n{bear_turn.text}",
            )
        _record_turn(record, ro_turn)
        deliberation.risk_officer = ro_turn.text

        async with scoped_session(PORTFOLIO_MANAGER.toolsets, creds) as (session, schemas):
            pm_turn = await run_turn(
                client, PORTFOLIO_MANAGER, session, schemas,
                brief
                + f"\n\nBull:\n{bull_turn.text}\n\nBear:\n{bear_turn.text}"
                + f"\n\nRisk Officer:\n{ro_turn.text}\n\n"
                "Decide: TAKE or PASS, and a quantity.",
            )
        _record_turn(record, pm_turn)
        deliberation.pm_decision = pm_turn.text

        # The PM is asked to open with TAKE or PASS. Read the first line rather than
        # scanning 400 characters of prose, where "pass" appears in ordinary sentences
        # ("I'll pass on sizing up", "passes the gate").
        pm_first = next((l.strip().upper() for l in pm_turn.text.splitlines() if l.strip()), "")
        pm_passed = pm_first.replace("*", "").lstrip("#").strip().startswith("PASS") or (
            "DECISION: PASS" in pm_turn.text.upper()[:200]
        )
        if pm_passed or deliberation.bear_verdict == "KILL":
            deliberation.final_gate = {
                "approved": False,
                "blocked_by": ["COMMITTEE"],
                "reasons": ["The committee declined — see the PM decision and the Bear's verdict."],
                "warnings": [], "summary": "BLOCKED by COMMITTEE",
            }
            continue

        # ── 4. FINAL GATE — deterministic, unconditional, no model in the loop ─────
        final = evaluate(
            proposal, snapshot.portfolio, risk, now if rehearse else datetime.now().astimezone(),
            kill_switch=kill_switch, market_open=gates_see_open,
            recent_fingerprints=recent,
            switch_reason=switches.block_reason(proposal.strategy),
        )
        deliberation.final_gate = _gate_dict(final)
        if not final.approved:
            continue

        # ── 5. Execute ────────────────────────────────────────────────────────────
        if dry_run:
            deliberation.execution_note = "DRY RUN — approved but not sent to the broker."
            continue

        async with scoped_session(EXECUTOR.toolsets, creds) as (session, schemas):
            exec_turn = await run_turn(
                client, EXECUTOR, session, schemas,
                "Place exactly this structure as ONE multi-leg order via place_option_order. "
                "Do not alter strikes, quantity or structure.\n\n"
                + json.dumps(deliberation.structure, indent=2),
            )
        _record_turn(record, exec_turn)
        deliberation.execution_note = exec_turn.text
        placed = any(c.tool == "place_option_order" and not c.result.startswith(("ERROR", "DENIED"))
                     for c in exec_turn.tool_calls)
        deliberation.executed = placed
        if placed:
            record.orders_placed += 1
            recent.append((proposal.fingerprint, proposal.expiry))

    record.deliberations = [asdict(d) for d in deliberations]
    record.finished_at = datetime.now().astimezone().isoformat()
    return record
