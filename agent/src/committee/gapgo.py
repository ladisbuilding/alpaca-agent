"""Small-cap gap-and-go: opening-range breakout on names already in play.

**Evidenced across eleven years, which is why it exists and RSI(2) does not.**

    2016 +0.204R   2019 +0.234R   2022 +0.126R   2025 +0.041R
    2017 +0.132R   2020 +0.097R   2023 +0.258R   2026 +0.131R
    2018 +0.268R   2021 -0.236R   2024 +0.270R
    ALL YEARS  n=774  mean +0.142R  t=+2.94   — positive in 10 of 11 years

The sibling strategy (`reversion.py`) looked BETTER than this over six months and was negative
in 9 of 11 years once the whole record was tested. Six months could not tell them apart.

⚠️ **The edge sits on top of its own cost.** Break-even slippage is ~0.6% and the measured
median round-trip spread on these names at the entry minute is **0.627%**. The median hides
everything that matters: **p10 is 0.26%, p90 is 1.80%**, and at ~0.9% per side the strategy
loses money. So `MAX_SPREAD` is not a refinement — it is the strategy. Trading every setup
means funding the tight ones with the wide ones.

⚠️ Honest limits carried forward:
* Early backtest years are FLATTERED — 2016 trades were charged a spread measured in 2026,
  and spreads have tightened a lot since.
* Crowding is visible: qualifying gappers went 148 (2016) -> 1,748 (2025), and 2025 is the
  weakest positive year.
* Stops are modelled filling AT the stop price; a reversing low-float runner slips worse.
* LULD halts are not modelled at all.

Deterministic, like the gates: a range, a break, a stop, a target. No model in the loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

# Screen — Ross Cameron's stated filters, as close as public data allows. Float is not
# available from Alpaca, so dollar volume and relative volume stand in for "in play".
MIN_GAP = 0.10
PRICE_LO, PRICE_HI = 1.0, 20.0
MIN_DOLLAR_VOLUME = 10_000_000
MIN_RVOL = 5.0

# The setup.
OR_MINUTES = 5
REWARD_RISK = 2.0

# ⚠️ THE binding constraint. See the module docstring: this is what decides whether the
# strategy is profitable, not the entry rule.
MAX_SPREAD = 0.006


@dataclass(frozen=True)
class OpeningRange:
    symbol: str
    high: float
    low: float
    bars: int

    @property
    def valid(self) -> bool:
        return self.high > self.low > 0 and self.bars >= OR_MINUTES

    @property
    def width_pct(self) -> float:
        return (self.high - self.low) / self.low if self.low else 0.0


@dataclass(frozen=True)
class Setup:
    symbol: str
    entry: float  # break of the range high
    stop: float  # range low
    target: float
    spread: float  # measured round-trip, as a fraction of mid
    gap: float
    rvol: float

    @property
    def risk_per_share(self) -> float:
        return self.entry - self.stop

    @property
    def reward_risk(self) -> float:
        return (self.target - self.entry) / self.risk_per_share if self.risk_per_share else 0.0

    def describe(self) -> str:
        return (
            f"{self.symbol}: gapped {self.gap:+.1%} on {self.rvol:.0f}x volume; "
            f"5-min range {self.stop:,.2f}-{self.entry:,.2f}, "
            f"stop {self.stop:,.2f}, target {self.target:,.2f} "
            f"({self.reward_risk:.1f}R), spread {self.spread:.2%}"
        )


def qualifies(*, gap: float, open_price: float, volume: float, rvol: float) -> bool:
    """Is this name in play at the open? Screen only — says nothing about tradability."""
    return (
        gap >= MIN_GAP
        and PRICE_LO <= open_price <= PRICE_HI
        and open_price * volume >= MIN_DOLLAR_VOLUME
        and rvol >= MIN_RVOL
    )


def opening_range(symbol: str, bars: Sequence[dict]) -> OpeningRange:
    """High and low of the first OR_MINUTES bars of the session.

    ⚠️ `bars` must START at the open. A series that begins late produces a narrower range,
    which silently becomes a different (tighter, earlier) trade rather than an error.
    """
    window = list(bars)[:OR_MINUTES]
    if not window:
        return OpeningRange(symbol, 0.0, 0.0, 0)
    return OpeningRange(
        symbol,
        max(float(b["h"]) for b in window),
        min(float(b["l"]) for b in window),
        len(window),
    )


def build_setup(
    rng: OpeningRange, *, spread: float, gap: float, rvol: float
) -> Setup | None:
    """The tradeable setup, or None if it fails the spread floor or the range is degenerate.

    Rejecting on spread happens HERE rather than downstream, because a setup we would not
    trade should never reach sizing — an edge you cannot collect is not an edge, and pricing
    it invites someone to act on it.
    """
    if not rng.valid or spread > MAX_SPREAD:
        return None
    risk = rng.high - rng.low
    if risk <= 0:
        return None
    return Setup(
        symbol=rng.symbol,
        entry=rng.high,
        stop=rng.low,
        target=rng.high + REWARD_RISK * risk,
        spread=spread,
        gap=gap,
        rvol=rvol,
    )


def triggered(setup: Setup, bar: dict) -> bool:
    """Has price broken the range high on this bar?"""
    return float(bar.get("h", 0)) > setup.entry
