"""Position management — deterministic exit rules.

The desk's mandate is to be in the market *and manage what it holds well*. Until now the
committee could only open: a structure entered on Monday would simply run to expiry, unmanaged.
That is a gap on two fronts. The brief explicitly asks an agent to demonstrate that it
"manages positions", and more practically, holding a short leg into expiry is how a
defined-risk trade stops being defined:

    "Pin risk: ~10% chance of closing 753-758 → assignment of $75,800 SPY on a $100k book,
     worthless wing. **'Defined risk' ends at 4pm.**"   — the Bear, 2026-08-25

So exits are rules, not judgment, and they run before any new position is considered. No model
in the loop, same as the gates and the audit: a model that can talk itself out of a stop is
not a stop.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Sequence


class ExitReason(str, Enum):
    PROFIT_TARGET = "profit_target"
    STOP_LOSS = "stop_loss"
    TIME_STOP = "time_stop"
    ASSIGNMENT_RISK = "assignment_risk"
    KILL_SWITCH = "kill_switch"
    STRATEGY_KILLED = "strategy_killed"


@dataclass(frozen=True)
class ManageConfig:
    """Standard defined-risk management, deliberately unclever.

    The profit target exists because the last of a credit spread's value is the slowest and
    riskiest to earn: holding from 50% to 100% of max profit risks the whole position to
    collect the remainder. Closing early converts an unrealised edge into a realised one and
    frees the buying power.
    """

    take_profit_pct: float = 0.50  # close at 50% of max profit
    stop_loss_multiple: float = 2.0  # close if the loss reaches 2x the credit taken
    close_at_dte: int = 1  # never hold a short leg into expiry — see the Bear, above
    # A short strike this close to spot at low DTE is an assignment risk regardless of the
    # long wing, because assignment happens overnight and the wing does not.
    assignment_moneyness_pct: float = 0.005


@dataclass(frozen=True)
class HeldPosition:
    """One structure the committee opened, as it stands now."""

    fingerprint: str
    underlying: str
    strategy: str
    expiry: date
    entry_credit: float  # positive for credit structures, negative for debit
    max_profit: float
    max_loss: float
    current_value: float  # cost to close now; positive = we would pay to exit
    short_strikes: tuple[float, ...] = ()

    def dte(self, today: date) -> int:
        return (self.expiry - today).days

    @property
    def is_credit(self) -> bool:
        return self.entry_credit > 0

    @property
    def unrealized(self) -> float:
        """Profit if we closed right now.

        A credit structure was paid `entry_credit` and costs `current_value` to buy back.
        A debit structure paid `-entry_credit` and is worth `current_value` to sell.
        """
        if self.is_credit:
            return self.entry_credit - self.current_value
        return self.current_value - abs(self.entry_credit)


@dataclass
class ExitDecision:
    position: HeldPosition
    reason: ExitReason
    detail: str

    def summary(self) -> str:
        return f"CLOSE {self.position.underlying} {self.position.strategy}: {self.reason.value} — {self.detail}"


def evaluate_exit(
    position: HeldPosition,
    today: date,
    config: ManageConfig | None = None,
    *,
    spot: float | None = None,
    kill_switch: bool = False,
    flatten: bool = False,
) -> ExitDecision | None:
    """Should this position be closed? Rules only, checked in order of urgency."""
    config = config or ManageConfig()
    dte = position.dte(today)

    if kill_switch:
        return ExitDecision(position, ExitReason.KILL_SWITCH, "Kill switch engaged — flatten.")

    if flatten:
        return ExitDecision(
            position,
            ExitReason.STRATEGY_KILLED,
            f"The {position.strategy} family is KILLED — flattening rather than carrying it.",
        )

    # ── assignment risk — the one that stops "defined risk" being true ────────────
    if dte <= config.close_at_dte and position.short_strikes and spot:
        for strike in position.short_strikes:
            distance = abs(strike - spot) / spot
            if distance <= config.assignment_moneyness_pct:
                return ExitDecision(
                    position,
                    ExitReason.ASSIGNMENT_RISK,
                    f"Short {strike:g} is {distance:.2%} from spot {spot:g} at {dte} DTE. "
                    "An assigned short leg is a stock position overnight; the long wing does "
                    "not cover that.",
                )

    # ── time stop ─────────────────────────────────────────────────────────────────
    if dte <= config.close_at_dte:
        return ExitDecision(
            position,
            ExitReason.TIME_STOP,
            f"{dte} DTE. Closing rather than carrying a short leg into expiry.",
        )

    # ── profit target ─────────────────────────────────────────────────────────────
    if position.max_profit > 0:
        target = position.max_profit * config.take_profit_pct
        if position.unrealized >= target:
            return ExitDecision(
                position,
                ExitReason.PROFIT_TARGET,
                f"Up ${position.unrealized:,.2f} of ${position.max_profit:,.2f} max "
                f"({position.unrealized / position.max_profit:.0%}). The remainder is the "
                "slowest and riskiest part to earn.",
            )

    # ── stop loss ─────────────────────────────────────────────────────────────────
    # Measured against the credit taken for a credit structure, and against the debit paid
    # for a debit one — in both cases, against what the trade actually put at stake.
    basis = abs(position.entry_credit)
    if basis > 0 and position.unrealized <= -basis * config.stop_loss_multiple:
        return ExitDecision(
            position,
            ExitReason.STOP_LOSS,
            f"Down ${abs(position.unrealized):,.2f} against ${basis:,.2f} at risk "
            f"({abs(position.unrealized) / basis:.1f}x). Cutting before it reaches max loss.",
        )

    return None


def review(
    positions: Sequence[HeldPosition],
    today: date,
    config: ManageConfig | None = None,
    *,
    spots: dict[str, float] | None = None,
    kill_switch: bool = False,
    switches=None,
) -> list[ExitDecision]:
    """Every position, checked every cycle. Exits run before new entries are considered —
    freeing risk and buying power matters more than adding to the book."""
    spots = spots or {}
    out = []
    for p in positions:
        decision = evaluate_exit(
            p, today, config,
            spot=spots.get(p.underlying.upper()),
            kill_switch=kill_switch,
            flatten=bool(switches and switches.must_flatten(p.strategy)),
        )
        if decision:
            out.append(decision)
    return out


def held_positions(
    broker_positions: Sequence[dict],
    executed_decisions: Sequence[dict],
) -> list[HeldPosition]:
    """Reconstruct what we hold by matching broker legs to the decisions that opened them.

    The broker reports one row per option leg with no memory of the structure it belongs to.
    The decision log is what knows a set of four legs was one iron condor entered for a $72
    credit — so exits can only be evaluated by joining the two. A four-leg condor is ONE
    position, not four, and counting legs is the same error family that once turned 15
    decisions into 72 "trades".

    Legs the decision log cannot explain are deliberately skipped rather than guessed at;
    the Auditor reports them separately as orphans.
    """
    by_symbol: dict[str, dict] = {p.get("symbol", ""): p for p in broker_positions}
    out: list[HeldPosition] = []

    for d in executed_decisions:
        s = d.get("structure") or {}
        legs = s.get("legs") or []
        if not legs:
            continue
        live = [by_symbol[l["symbol"]] for l in legs if l.get("symbol") in by_symbol]
        if not live:
            continue  # already closed or expired — nothing to manage

        # Net market value across the legs. Negative on a credit structure (we are net
        # short), so the cost to close is its magnitude.
        net_value = sum(float(p.get("market_value", 0) or 0) for p in live)
        credit = float(s.get("net_credit", 0) or 0)

        try:
            expiry = date.fromisoformat(s["expiry"])
        except (KeyError, ValueError):
            continue

        out.append(
            HeldPosition(
                fingerprint=s.get("fingerprint", ""),
                underlying=s.get("underlying", "?"),
                strategy=d.get("strategy", "unknown"),
                expiry=expiry,
                entry_credit=credit,
                max_profit=float(s.get("max_profit", 0) or 0),
                max_loss=float(s.get("max_loss", 0) or 0),
                current_value=abs(net_value),
                short_strikes=tuple(
                    float(l["strike"]) for l in legs if l.get("side") == "sell" and "strike" in l
                ),
            )
        )
    return out
