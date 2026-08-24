"""Deterministic risk gates.

This module is the committee's hard floor. It contains NO model calls and no I/O — it is
pure, synchronous, unit-tested code. Alpaca's own reference architecture states the rule
this module exists to satisfy:

    "Risk checks run as deterministic code, unit-tested, with no model in the loop."

The LLM agents (Scouts, Bull, Bear, Portfolio Manager) can propose anything they like.
Nothing reaches the broker unless `evaluate()` returns a result whose `approved` is True.
The advocate agents additionally run against MCP servers with the `trading` toolset omitted,
so they cannot place an order even if they tried — see docs/ARCHITECTURE.md.

Every gate returns a *reason string* when it blocks. Those strings are written to the
decision log and surfaced on the dashboard: a refusal is a first-class, explainable outcome,
not a silent no-op.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Iterable, Sequence


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class Right(str, Enum):
    CALL = "call"
    PUT = "put"


@dataclass(frozen=True)
class Leg:
    """One option contract leg of a proposed structure."""

    symbol: str  # OCC symbol, e.g. QQQ260826P00696000
    side: Side
    qty: int
    right: Right
    strike: float
    expiry: date

    def __post_init__(self) -> None:
        if self.qty <= 0:
            raise ValueError(f"leg qty must be positive, got {self.qty}")


@dataclass(frozen=True)
class Proposal:
    """A trade the committee wants to place.

    `max_loss` is the worst-case dollar loss of the structure at expiry, already multiplied
    by contract size and quantity. It must be supplied by the strategy layer and is
    independently re-derived by `verify_defined_risk` for vertical/condor structures — a
    strategy that miscomputes its own risk is exactly the failure this gate exists to catch.
    """

    underlying: str
    strategy: str  # e.g. "iron_condor", "put_credit_spread", "long_call"
    legs: tuple[Leg, ...]
    max_loss: float  # positive dollars
    max_profit: float  # positive dollars
    net_credit: float  # positive = credit received, negative = debit paid
    bid_ask_pct: float = 0.0  # width of the structure's spread as a fraction of its mid

    @property
    def expiry(self) -> date:
        return max(leg.expiry for leg in self.legs)

    @property
    def fingerprint(self) -> str:
        """Identity of the *opportunity*, not of the order.

        Two proposals share a fingerprint when they are the same structure on the same
        underlying at the same strikes and expiry. This is what the dedup gate keys on —
        see `DEDUP` in the gate list for why the window is tied to expiry.
        """
        strikes = ",".join(
            f"{leg.right.value}{leg.strike:g}{leg.side.value[0]}" for leg in sorted(self.legs, key=lambda l: (l.right.value, l.strike))
        )
        return f"{self.underlying}|{self.strategy}|{self.expiry.isoformat()}|{strikes}"


@dataclass(frozen=True)
class OpenPosition:
    underlying: str
    strategy: str
    fingerprint: str
    max_loss: float
    expiry: date


@dataclass(frozen=True)
class PortfolioState:
    equity: float
    cash: float
    buying_power: float
    realized_pnl_today: float  # negative when down on the day
    open_positions: tuple[OpenPosition, ...] = ()

    @property
    def deployed_risk(self) -> float:
        return sum(p.max_loss for p in self.open_positions)


@dataclass(frozen=True)
class RiskConfig:
    """Hard limits. Deliberately conservative — see docs/ARCHITECTURE.md on why a
    reliably-green book beats a headline number when P&L is one of five judged criteria."""

    max_loss_per_trade_pct: float = 0.01  # 1% of equity
    max_deployed_risk_pct: float = 0.10  # 10% of equity at risk across all open positions
    max_concurrent_positions: int = 8
    max_positions_per_underlying: int = 2
    daily_loss_limit_pct: float = 0.03  # halt for the day after -3%
    min_credit_to_max_loss: float = 0.10  # reject credit spreads paying < 10% of risk
    max_bid_ask_pct: float = 0.15  # refuse to cross a spread wider than 15% of mid
    no_new_trades_within_minutes_of_close: int = 15
    buying_power_buffer: float = 0.20  # never consume the last 20% of buying power


@dataclass
class GateResult:
    approved: bool
    blocked_by: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def block(self, gate: str, reason: str) -> None:
        self.approved = False
        self.blocked_by.append(gate)
        self.reasons.append(reason)


CONTRACT_SIZE = 100
MARKET_CLOSE = time(16, 0)  # ET


def verify_defined_risk(proposal: Proposal) -> float | None:
    """Independently re-derive max loss for vertical-spread-shaped structures.

    Returns the derived max loss, or None when the shape isn't one we can verify.
    A structure whose every short leg is covered by a long leg at the same expiry and
    right has max loss = (widest wing width * contract size * qty) - net credit.

    This exists because `Proposal.max_loss` is supplied by the strategy layer, and a
    strategy that under-reports its own risk would otherwise sail through every
    percentage-based gate below.
    """
    by_right: dict[Right, list[Leg]] = {}
    for leg in proposal.legs:
        by_right.setdefault(leg.right, []).append(leg)

    width_by_right: dict[Right, float] = {}
    for right, legs in by_right.items():
        shorts = [l for l in legs if l.side is Side.SELL]
        longs = [l for l in legs if l.side is Side.BUY]
        if not shorts:
            continue
        if len(shorts) != len(longs):
            return None  # naked or ratioed — cannot verify, must be blocked upstream
        side_width = 0.0
        for short in shorts:
            # the protective long, further out of the money than the short
            if right is Right.PUT:
                covers = [l for l in longs if l.strike < short.strike]
            else:
                covers = [l for l in longs if l.strike > short.strike]
            if not covers:
                return None
            nearest = min(covers, key=lambda l: abs(l.strike - short.strike))
            side_width += abs(short.strike - nearest.strike) * short.qty
        width_by_right[right] = side_width

    if not width_by_right:
        return None

    # A two-sided structure (iron condor) can only finish in the money on ONE side,
    # provided the short strikes do not overlap. Summing both wings would overstate
    # max loss by ~2x and mis-size every downstream percentage cap.
    #
    # Overlapping shorts (a "guts"/inverted structure) CAN lose on both sides, so we
    # fall back to the sum there — the conservative reading.
    if len(width_by_right) == 2:
        highest_short_put = max(
            (l.strike for l in by_right[Right.PUT] if l.side is Side.SELL), default=float("-inf")
        )
        lowest_short_call = min(
            (l.strike for l in by_right[Right.CALL] if l.side is Side.SELL), default=float("inf")
        )
        if highest_short_put < lowest_short_call:
            worst_side = max(width_by_right.values())  # non-overlapping: one side only
        else:
            worst_side = sum(width_by_right.values())  # inverted: both sides can lose
    else:
        worst_side = sum(width_by_right.values())

    return worst_side * CONTRACT_SIZE - max(proposal.net_credit, 0.0)


def has_uncovered_short(proposal: Proposal) -> bool:
    """True when any short leg lacks a same-right long leg protecting it."""
    by_right: dict[Right, list[Leg]] = {}
    for leg in proposal.legs:
        by_right.setdefault(leg.right, []).append(leg)
    for right, legs in by_right.items():
        short_qty = sum(l.qty for l in legs if l.side is Side.SELL)
        long_qty = sum(l.qty for l in legs if l.side is Side.BUY)
        if short_qty > long_qty:
            return True
    return False


def evaluate(
    proposal: Proposal,
    portfolio: PortfolioState,
    config: RiskConfig,
    now: datetime,
    *,
    kill_switch: bool = False,
    market_open: bool = True,
    recent_fingerprints: Iterable[tuple[str, date]] = (),
) -> GateResult:
    """Run every gate. Gates do not short-circuit — we collect *all* blocking reasons so
    the decision log shows every rule a proposal violated, not just the first."""

    result = GateResult(approved=True)

    # ── KILL SWITCH ────────────────────────────────────────────────────────────────
    if kill_switch:
        result.block("KILL_SWITCH", "Kill switch engaged — no new positions.")

    # ── MARKET HOURS ───────────────────────────────────────────────────────────────
    if not market_open:
        result.block("MARKET_CLOSED", "Market is closed.")
    else:
        close_dt = datetime.combine(now.date(), MARKET_CLOSE, tzinfo=now.tzinfo)
        cutoff = close_dt - timedelta(minutes=config.no_new_trades_within_minutes_of_close)
        if now >= cutoff:
            result.block(
                "NEAR_CLOSE",
                f"Within {config.no_new_trades_within_minutes_of_close}m of the close "
                f"({now:%H:%M} >= {cutoff:%H:%M}) — liquidity thins and fills degrade.",
            )

    # ── DEFINED RISK ───────────────────────────────────────────────────────────────
    # Non-negotiable: the account must never carry an undefined-loss position.
    if has_uncovered_short(proposal):
        result.block(
            "UNDEFINED_RISK",
            f"{proposal.strategy} on {proposal.underlying} contains an uncovered short leg. "
            "Only defined-risk structures are permitted.",
        )

    if proposal.max_loss <= 0:
        result.block("UNDEFINED_RISK", f"max_loss must be positive, got {proposal.max_loss}.")

    derived = verify_defined_risk(proposal)
    if derived is not None and proposal.max_loss < derived - 0.01:
        result.block(
            "MISREPORTED_RISK",
            f"Proposal claims max loss ${proposal.max_loss:,.2f} but the structure's "
            f"geometry implies ${derived:,.2f}. Refusing to size off an under-reported number.",
        )

    # A debit structure's max loss is exactly the debit paid — no geometry needed. This is
    # the other half of the check above: verify_defined_risk() returns None for debit
    # verticals (the short sits further OTM than the long, so there is no protective leg
    # to measure against), which would otherwise leave them entirely unverified.
    if proposal.net_credit < 0:
        debit = abs(proposal.net_credit)
        if abs(proposal.max_loss - debit) > 0.01:
            result.block(
                "MISREPORTED_RISK",
                f"Debit structure paid ${debit:,.2f} but claims max loss "
                f"${proposal.max_loss:,.2f}. On a debit spread they are the same number.",
            )

    # ── PER-TRADE SIZE ─────────────────────────────────────────────────────────────
    per_trade_cap = portfolio.equity * config.max_loss_per_trade_pct
    if proposal.max_loss > per_trade_cap:
        result.block(
            "TRADE_TOO_LARGE",
            f"Max loss ${proposal.max_loss:,.2f} exceeds the per-trade cap "
            f"${per_trade_cap:,.2f} ({config.max_loss_per_trade_pct:.1%} of ${portfolio.equity:,.0f}).",
        )

    # ── DAILY LOSS LIMIT ───────────────────────────────────────────────────────────
    daily_cap = portfolio.equity * config.daily_loss_limit_pct
    if portfolio.realized_pnl_today <= -daily_cap:
        result.block(
            "DAILY_LOSS_LIMIT",
            f"Down ${abs(portfolio.realized_pnl_today):,.2f} today, at or beyond the "
            f"{config.daily_loss_limit_pct:.1%} limit (${daily_cap:,.2f}). Halted until tomorrow.",
        )

    # ── AGGREGATE DEPLOYED RISK ────────────────────────────────────────────────────
    deployed_cap = portfolio.equity * config.max_deployed_risk_pct
    if portfolio.deployed_risk + proposal.max_loss > deployed_cap:
        result.block(
            "PORTFOLIO_RISK_CAP",
            f"Would take total risk to ${portfolio.deployed_risk + proposal.max_loss:,.2f}, "
            f"over the ${deployed_cap:,.2f} cap ({config.max_deployed_risk_pct:.0%} of equity).",
        )

    # ── POSITION COUNT ─────────────────────────────────────────────────────────────
    if len(portfolio.open_positions) >= config.max_concurrent_positions:
        result.block(
            "TOO_MANY_POSITIONS",
            f"Already holding {len(portfolio.open_positions)} positions "
            f"(max {config.max_concurrent_positions}).",
        )

    # ── CONCENTRATION ──────────────────────────────────────────────────────────────
    same_underlying = sum(1 for p in portfolio.open_positions if p.underlying == proposal.underlying)
    if same_underlying >= config.max_positions_per_underlying:
        result.block(
            "CONCENTRATION",
            f"Already holding {same_underlying} positions in {proposal.underlying} "
            f"(max {config.max_positions_per_underlying}). Correlated risk.",
        )

    # ── DEDUP ──────────────────────────────────────────────────────────────────────
    # The window is the opportunity's LIFECYCLE — an identical structure at the same
    # expiry is the same opportunity until that expiry passes. A short convenience
    # window (e.g. 5 minutes) re-enters the same trade repeatedly and inflates apparent
    # activity; that failure previously turned 15 real decisions into 72 "trades" and a
    # $89 result into a reported $2,015. See docs/AUDIT.md.
    fp = proposal.fingerprint
    for seen_fp, seen_expiry in recent_fingerprints:
        if seen_fp == fp and seen_expiry >= now.date():
            result.block(
                "DUPLICATE",
                f"Identical structure already traded and still live until {seen_expiry}. "
                "Same opportunity, not a new one.",
            )
            break

    # ── EXECUTION QUALITY ──────────────────────────────────────────────────────────
    if proposal.bid_ask_pct > config.max_bid_ask_pct:
        result.block(
            "WIDE_SPREAD",
            f"Structure's bid/ask is {proposal.bid_ask_pct:.1%} of mid, over the "
            f"{config.max_bid_ask_pct:.0%} limit. The edge is inside the spread.",
        )

    # ── CREDIT QUALITY (credit structures only) ────────────────────────────────────
    if proposal.net_credit > 0 and proposal.max_loss > 0:
        ratio = proposal.net_credit / proposal.max_loss
        if ratio < config.min_credit_to_max_loss:
            result.block(
                "THIN_CREDIT",
                f"Collecting ${proposal.net_credit:,.2f} to risk ${proposal.max_loss:,.2f} "
                f"({ratio:.1%}), under the {config.min_credit_to_max_loss:.0%} floor. "
                "Not paid enough for the tail.",
            )

    # ── BUYING POWER ───────────────────────────────────────────────────────────────
    usable_bp = portfolio.buying_power * (1 - config.buying_power_buffer)
    if proposal.max_loss > usable_bp:
        result.block(
            "INSUFFICIENT_BUYING_POWER",
            f"Requires ${proposal.max_loss:,.2f} against ${usable_bp:,.2f} usable buying power "
            f"(keeping a {config.buying_power_buffer:.0%} buffer).",
        )

    # ── WARNINGS (never block) ─────────────────────────────────────────────────────
    if proposal.expiry <= now.date():
        result.warnings.append("Structure expires today — gamma risk is at its maximum.")
    if portfolio.realized_pnl_today < 0 and not result.blocked_by:
        result.warnings.append(
            f"Down ${abs(portfolio.realized_pnl_today):,.2f} today but inside the limit."
        )

    return result


def summarize(result: GateResult) -> str:
    """One-line human summary for the decision log and the daily social post."""
    if result.approved:
        suffix = f" ({len(result.warnings)} warning(s))" if result.warnings else ""
        return f"APPROVED{suffix}"
    return f"BLOCKED by {', '.join(result.blocked_by)}"
