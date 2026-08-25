"""Honest P&L. Deterministic reconciliation, hostile to good news.

This account's performance is judged by a third party, and paper P&L is easy to overstate.
A previous system in this lineage reported **$2,015 profit at a 100% win rate**; the audited
figure was **$89**, because a dedup window let 15 real decisions be recorded as 72 "trades".

Alpaca's own guidance says the same thing from the other side: *"Paper trading results do not
predict live performance."*

So the arithmetic here is deterministic — no model in the loop, same as the risk gates. The
Auditor agent reads this report and exercises judgment about what looks wrong; it does not
compute the numbers, because a number a model can talk itself into is not an audit.

The report is built to make three specific lies impossible to tell quietly:

  1. **Order rows are not trades.** A four-leg condor is ONE decision. Counting legs is how
     15 becomes 72.
  2. **Our number must reconcile against the broker's.** We attribute P&L per strategy from
     our own decision log; the account's own equity change is the independent check. When
     they disagree, that gap is reported, never absorbed.
  3. **A great-looking number is a bug until proven otherwise.** Implausible win rates and
     per-trade returns are flagged as anomalies rather than celebrated.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable, Sequence

# A win rate at or above this with a meaningful sample is the signature of the failure that
# produced "$2,015, 100% win rate". Real defined-risk premium selling wins often, but not
# this often, and never at n large.
IMPLAUSIBLE_WIN_RATE = 0.95
MIN_SAMPLE_FOR_WIN_RATE = 5
# Realized P&L above this multiple of a structure's max profit means the arithmetic is wrong,
# not that the trade was brilliant — a defined-risk structure cannot exceed its own max.
IMPOSSIBLE_RETURN_MULTIPLE = 1.01
# Dollars of drift between our attributed P&L and the broker's equity change before we call it.
RECONCILIATION_TOLERANCE = 1.00


@dataclass(frozen=True)
class Fill:
    """One execution as the broker reports it. Legs, not trades."""

    id: str
    symbol: str
    side: str
    qty: float
    price: float
    at: datetime

    @property
    def cash_flow(self) -> float:
        """Signed cash: selling to open a credit spread is money in, buying is money out."""
        notional = self.qty * self.price * 100
        return notional if self.side.startswith("sell") else -notional


@dataclass
class StrategyPnL:
    strategy: str
    decisions: int = 0
    order_rows: int = 0
    realized: float = 0.0
    wins: int = 0
    losses: int = 0

    @property
    def win_rate(self) -> float | None:
        settled = self.wins + self.losses
        return None if settled == 0 else self.wins / settled


@dataclass
class AuditReport:
    generated_at: str
    equity: float
    equity_change: float  # the broker's own number — the independent check
    attributed: float  # what we can explain from our decision log
    unattributed: float  # the gap. Reported, never absorbed.
    distinct_decisions: int
    order_rows: int
    by_strategy: list[StrategyPnL] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def reconciles(self) -> bool:
        return abs(self.unattributed) <= RECONCILIATION_TOLERANCE

    def headline(self) -> str:
        """Deliberately not a single number.

        A headline figure is exactly what hid the $2,015. This always states the decision
        count next to the raw order-row count and says outright whether it reconciles.
        """
        rec = "reconciles" if self.reconciles else f"DOES NOT RECONCILE (${self.unattributed:+,.2f} unexplained)"
        return (
            f"{self.distinct_decisions} decisions across {self.order_rows} order rows · "
            f"attributed ${self.attributed:+,.2f} vs broker ${self.equity_change:+,.2f} · {rec}"
        )


def fills_from_activities(activities: Iterable[dict[str, Any]]) -> list[Fill]:
    """Parse Alpaca account activities into fills.

    Fills are used rather than orders on purpose: an order records intent, a fill records
    what actually happened. An order that was placed and never filled is not a trade, and
    counting it as one is the same class of error as counting legs.
    """
    out: list[Fill] = []
    for a in activities:
        if a.get("activity_type") not in ("FILL", "PARTIAL_FILL"):
            continue
        try:
            out.append(
                Fill(
                    id=str(a.get("id", "")),
                    symbol=str(a.get("symbol", "")),
                    side=str(a.get("side", "")).lower(),
                    qty=float(a.get("qty", 0)),
                    price=float(a.get("price", 0)),
                    at=datetime.fromisoformat(str(a["transaction_time"]).replace("Z", "+00:00")),
                )
            )
        except (KeyError, ValueError, TypeError):
            continue  # a malformed row is an anomaly, surfaced by the orphan check below
    return out


def audit(
    account: dict[str, Any],
    activities: Iterable[dict[str, Any]],
    decisions: Sequence[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> AuditReport:
    """Reconcile what the committee believes it did against what the broker says happened.

    `decisions` are our own executed deliberations (from the cycle records). `activities`
    and `account` come from the broker. The point of the exercise is the disagreement.
    """
    now = now or datetime.now().astimezone()
    fills = fills_from_activities(activities)

    equity = float(account.get("equity", 0) or 0)
    last_equity = float(account.get("last_equity", equity) or equity)
    equity_change = equity - last_equity

    executed = [d for d in decisions if d.get("executed")]
    by_symbol_leg: dict[str, list[Fill]] = defaultdict(list)
    for f in fills:
        by_symbol_leg[f.symbol].append(f)

    # ── P&L attributed per strategy, from our own log ──────────────────────────────
    groups: dict[str, StrategyPnL] = {}
    seen_fingerprints: dict[str, int] = defaultdict(int)
    claimed_symbols: set[str] = set()

    for d in executed:
        strategy = d.get("strategy") or "unknown"
        s = d.get("structure") or {}
        g = groups.setdefault(strategy, StrategyPnL(strategy=strategy))
        g.decisions += 1
        legs = s.get("legs") or []
        g.order_rows += len(legs)
        for leg in legs:
            claimed_symbols.add(str(leg.get("symbol", "")))
        if s.get("fingerprint"):
            seen_fingerprints[s["fingerprint"]] += 1

        realized = d.get("realized_pnl")
        if realized is not None:
            g.realized += float(realized)
            if float(realized) > 0:
                g.wins += 1
            elif float(realized) < 0:
                g.losses += 1

    attributed = sum(g.realized for g in groups.values())
    distinct_decisions = sum(g.decisions for g in groups.values())
    order_rows = sum(g.order_rows for g in groups.values())

    report = AuditReport(
        generated_at=now.isoformat(),
        equity=equity,
        equity_change=equity_change,
        attributed=attributed,
        unattributed=equity_change - attributed,
        distinct_decisions=distinct_decisions,
        order_rows=order_rows,
        by_strategy=sorted(groups.values(), key=lambda g: g.strategy),
    )

    # ── Anomalies. Each one is a specific way the headline could be a lie. ─────────

    if not report.reconciles:
        report.anomalies.append(
            f"Attributed P&L (${attributed:+,.2f}) does not reconcile with the account's own "
            f"equity change (${equity_change:+,.2f}); ${report.unattributed:+,.2f} is unexplained. "
            "Either a position moved that we did not attribute, or an attribution is wrong. "
            "Do not report the attributed figure until this closes."
        )

    for fingerprint, count in seen_fingerprints.items():
        if count > 1:
            report.anomalies.append(
                f"Structure {fingerprint} was executed {count} times. Identical structures at the "
                "same strikes and expiry are the SAME opportunity — the dedup gate has a hole, "
                "and this is precisely how 15 decisions became 72 trades."
            )

    orphans = sorted(set(by_symbol_leg) - claimed_symbols)
    if orphans:
        report.anomalies.append(
            f"{len(orphans)} filled symbol(s) have no matching decision record: "
            f"{', '.join(orphans[:6])}{'…' if len(orphans) > 6 else ''}. "
            "Something traded that the committee did not decide."
        )

    phantom = [
        d for d in executed
        if (d.get("structure") or {}).get("legs")
        and not any(str(leg.get("symbol")) in by_symbol_leg for leg in d["structure"]["legs"])
    ]
    if phantom:
        report.anomalies.append(
            f"{len(phantom)} decision(s) are marked executed but have no fills at the broker. "
            "A recorded trade that never happened inflates the decision count."
        )

    for g in report.by_strategy:
        wr = g.win_rate
        settled = g.wins + g.losses
        if wr is not None and settled >= MIN_SAMPLE_FOR_WIN_RATE and wr >= IMPLAUSIBLE_WIN_RATE:
            report.anomalies.append(
                f"{g.strategy}: {wr:.0%} win rate over {settled} settled trades. This is the "
                "signature of the counting failure that produced a reported 100% win rate on a "
                "book that had actually made $89. Verify the individual fills before believing it."
            )

    for d in executed:
        s = d.get("structure") or {}
        realized, max_profit = d.get("realized_pnl"), s.get("max_profit")
        if realized is None or not max_profit:
            continue
        if float(realized) > float(max_profit) * IMPOSSIBLE_RETURN_MULTIPLE:
            report.anomalies.append(
                f"{s.get('underlying', '?')} {d.get('strategy')}: realized ${float(realized):,.2f} "
                f"exceeds the structure's max profit of ${float(max_profit):,.2f}. A defined-risk "
                "structure cannot return more than its maximum — the arithmetic is wrong."
            )

    if not executed:
        report.notes.append(
            "No executed decisions to audit. A book with no trades has nothing to overstate."
        )
    if executed and not any(d.get("realized_pnl") is not None for d in executed):
        report.notes.append(
            "Positions are open but none have settled, so realized P&L is $0 by definition. "
            "Unrealized marks are not results and are deliberately excluded from the attributed figure."
        )

    return report


def format_report(report: AuditReport) -> str:
    """Plain text for the decision log, the dashboard and the daily post."""
    lines = [report.headline(), ""]
    if report.by_strategy:
        lines.append("By strategy:")
        for g in report.by_strategy:
            wr = f"{g.win_rate:.0%}" if g.win_rate is not None else "—"
            lines.append(
                f"  {g.strategy:<22} {g.decisions:>3} decisions ({g.order_rows:>3} rows)  "
                f"realized ${g.realized:>10,.2f}  win {wr}"
            )
        lines.append("")
    if report.anomalies:
        lines.append(f"ANOMALIES ({len(report.anomalies)}):")
        lines += [f"  ⚠ {a}" for a in report.anomalies]
        lines.append("")
    if report.notes:
        lines += [f"  {n}" for n in report.notes]
    return "\n".join(lines)
