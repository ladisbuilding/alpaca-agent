"""Which edge exists today — measured at the horizon actually traded.

Deterministic, no model in the loop, same rule as the gates and the audit. Whether the
strategy's premise holds is arithmetic, and arithmetic should not be negotiable.

⚠️ **This module was wrong once, and the way it was wrong is worth keeping written down.**

The first version compared *annualised* implied volatility against *30-day* realised
volatility. That is a fair test for a multi-week structure. It is the wrong test for the
2-DTE structures this agent actually trades, and it produced a confident, false conclusion:
"no premium edge anywhere". The committee then correctly refused every trade for two days.

Measured at the horizon actually traded, the picture inverted:

    IWM 2DTE   implied move 1.47x actual sigma   breached 11% of windows
    SPY 2DTE   implied move 1.25x actual sigma   breached 22%
    QQQ 2DTE   implied move 0.96x actual sigma   breached 30%   <- fairly priced

And QQQ — the one genuinely fairly priced — was what the scouts kept nominating.

**The statistic that decides is the BREACH RATE.** An at-the-money implied move is
approximately a one-sigma move, so if options were fairly priced roughly 32% of periods
would exceed it. Fewer breaches than that means sellers are being overpaid; more means
buyers are. Unlike a ratio of volatilities, this compares like with like: a move the market
priced against moves that actually happened, over the same number of days.

⚠️ Honest limits, since this has been wrong in both directions:
* Windows overlap, so they are not independent observations.
* It reads one current IV snapshot, not a historical implied series.
* A low breach rate does not prove positive expectancy — losses can exceed wins per event.
  `THIN_CREDIT` is what tests whether the credit actually pays for the risk, and it stays.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

# A 1-sigma move is exceeded ~31.7% of the time under a normal distribution. Real returns
# are fat-tailed, which if anything pushes the fair breach rate slightly higher — so a rate
# well BELOW this is the conservative direction to call a seller edge.
FAIR_BREACH = 0.32
SELLER_EDGE_BELOW = 0.25
BUYER_EDGE_ABOVE = 0.40
# Below this many windows the breach rate is noise, not a measurement.
MIN_WINDOWS = 25


class Regime(str, Enum):
    PREMIUM_RICH = "premium_rich"
    NO_EDGE = "no_edge"
    PREMIUM_CHEAP = "premium_cheap"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RegimeRead:
    underlying: str
    regime: Regime
    dte: int | None = None
    implied_move: float | None = None
    actual_sigma: float | None = None
    breach_rate: float | None = None
    windows: int = 0

    @property
    def ratio(self) -> float | None:
        if not self.implied_move or not self.actual_sigma:
            return None
        return self.implied_move / self.actual_sigma

    @property
    def sleeve(self) -> str:
        return {
            Regime.PREMIUM_RICH: "income",
            Regime.PREMIUM_CHEAP: "long_premium",
            Regime.NO_EDGE: "none",
            Regime.UNKNOWN: "none",
        }[self.regime]

    def explain(self) -> str:
        if self.regime is Regime.UNKNOWN or self.breach_rate is None:
            return f"{self.underlying}: regime unknown (insufficient data)"
        base = (
            f"{self.underlying} at {self.dte}DTE: the market prices a {self.implied_move:.2%} move; "
            f"the underlying actually exceeded that in {self.breach_rate:.0%} of "
            f"{self.windows} windows (fair value ~{FAIR_BREACH:.0%})"
        )
        if self.regime is Regime.PREMIUM_RICH:
            return (
                f"{base} — premium is RICH. Sellers are being paid more than the underlying "
                "delivers. Defined-risk premium selling is justified here."
            )
        if self.regime is Regime.PREMIUM_CHEAP:
            return (
                f"{base} — premium is CHEAP. The underlying moves further than the market "
                "prices. Buy premium (debit verticals, calendars) rather than sell it."
            )
        return (
            f"{base} — FAIRLY PRICED. Neither side is being overpaid, so neither selling nor "
            "buying premium has an edge here. Standing down is the correct default."
        )


def classify(
    underlying: str,
    atm_iv: float | None,
    dte: int | None,
    closes: Sequence[float],
) -> RegimeRead:
    """Is short-dated premium rich, cheap, or fair on this underlying right now?

    `atm_iv` is the at-the-money implied vol on the expiry being traded and `dte` its days to
    expiry — both must describe the SAME structure, or this compares a price from one horizon
    against moves from another, which is the error this module was written to fix.
    """
    if not atm_iv or not dte or dte <= 0 or len(closes) < MIN_WINDOWS + dte:
        return RegimeRead(underlying, Regime.UNKNOWN)

    implied_move = atm_iv * (dte / 252) ** 0.5

    # Actual moves over the SAME number of sessions the option has left to live.
    returns = [(closes[i] - closes[i - dte]) / closes[i - dte] for i in range(dte, len(closes))]
    if len(returns) < MIN_WINDOWS:
        return RegimeRead(underlying, Regime.UNKNOWN)

    sigma = statistics.pstdev(returns)
    breach = sum(1 for r in returns if abs(r) > implied_move) / len(returns)

    if breach < SELLER_EDGE_BELOW:
        regime = Regime.PREMIUM_RICH
    elif breach > BUYER_EDGE_ABOVE:
        regime = Regime.PREMIUM_CHEAP
    else:
        regime = Regime.NO_EDGE

    return RegimeRead(
        underlying=underlying,
        regime=regime,
        dte=dte,
        implied_move=implied_move,
        actual_sigma=sigma,
        breach_rate=breach,
        windows=len(returns),
    )
