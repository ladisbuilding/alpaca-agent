"""RSI(2) mean reversion on bond / international / small-cap ETFs.

**The claim, stated so it can be attacked:** short-horizon mean reversion still pays where
arbitrage capital is thin, and is gone where it is thick. Measured 2026-02-06 -> 2026-08-30:

    THIN  (LQD HYG TLT IEF EFA EEM IWM)   n=951  mean +0.076%/trade  pooled t=+3.74
    THICK (SPY QQQ XLK XLF DIA ...)       n=690  mean +0.053%/trade  pooled t=+1.37

⭐ What makes this worth trading rather than another sweep artifact: the thin/thick split was
**predicted by an earlier 12-symbol run and then confirmed on assets that run never saw.** In
the 216-test sweep it appears in (`scripts/sweep_strategies.py`), Benjamini-Hochberg at 10%
returned **ZERO** discoveries — gold, silver, miners, oil, crypto, leveraged ETFs, trend
following and swing momentum all failed. This survived because it was a hypothesis first.

⚠️ **Known weaknesses, kept here so nobody has to rediscover them** (see docs/STRATEGY-BRIEF.md):
* **RSI(2) is Larry Connors' published strategy from the 2000s** and its decay is documented.
  A public, profitable rule invites the question of why it has not been arbitraged away.
* Only ~6 months and 57-79 signals per asset. One regime.
* Commodities that I *labelled* thin-arbitrage (SLV, GDX, XLU, XLE) came out NEGATIVE, so the
  boundary was drawn partly after seeing results. The honest core is bonds + international.
* Windows overlap, so the t-statistics are optimistic.
* Backtest Sharpe ~3.9 is **not credible** — expect real degradation. Trade small and measure
  it rather than sizing off the backtest.
* The short side carries borrow cost, which is not in the measured numbers.
* Bond ETF spreads widen exactly when this strategy wants to buy.

The rules are deliberately trivial: entry on a threshold, exit on the clock. There is no
parameter to drift and nothing for a model to improvise.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

# Bonds, international, small caps. NOT commodities — those measured negative, and the
# universe is the hypothesis, so it does not get quietly widened later.
BASKET = ("LQD", "HYG", "TLT", "IEF", "EFA", "EEM", "IWM")

OVERSOLD = 10.0
OVERBOUGHT = 90.0
RSI_PERIOD = 2
# Below this the indicator is undefined rather than merely noisy.
MIN_CLOSES = RSI_PERIOD + 1


@dataclass(frozen=True)
class Signal:
    symbol: str
    direction: str  # "long" | "short"
    rsi: float
    ref_price: float

    def describe(self) -> str:
        return (
            f"{self.symbol}: RSI(2) = {self.rsi:.1f} "
            f"({'oversold' if self.direction == 'long' else 'overbought'}) "
            f"-> {self.direction} at ~${self.ref_price:,.2f}, exit at the next close"
        )


def rsi(closes: Sequence[float], period: int = RSI_PERIOD) -> float | None:
    """Wilder RSI over `period` bars. None when there is not enough history."""
    if len(closes) < period + 1:
        return None
    gains = losses = 0.0
    for i in range(len(closes) - period, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains += max(delta, 0.0)
        losses += max(-delta, 0.0)
    # ⚠️ A flat series has NO gains and NO losses, and the usual `losses == 0 -> 100`
    # shortcut then reports maximum overbought on a price that has not moved at all —
    # which fired a short signal on a constant series the first time this was exercised.
    # Undefined is 50, not 100.
    if losses == 0 and gains == 0:
        return 50.0
    if losses == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + gains / losses)


def signal_for(symbol: str, closes: Sequence[float]) -> Signal | None:
    """The signal as of the LAST close in `closes`, or None if there is no edge today.

    ⚠️ `closes` must end with the session being acted on. Passing a series that ends
    yesterday produces yesterday's signal, silently and with no error — the entry is a
    threshold on the final bar, so an off-by-one here is a wrong trade, not a crash.
    """
    if len(closes) < MIN_CLOSES:
        return None
    value = rsi(closes)
    if value is None:
        return None
    price = closes[-1]
    if price <= 0:
        return None
    if value < OVERSOLD:
        return Signal(symbol, "long", value, price)
    if value > OVERBOUGHT:
        return Signal(symbol, "short", value, price)
    return None


def scan(closes_by_symbol: dict[str, Sequence[float]]) -> list[Signal]:
    """Every signal in the basket today, strongest first.

    Ranked by distance from the neutral 50, so the most stretched name is sized first when
    the risk budget cannot cover all of them.
    """
    out = [
        s
        for sym in BASKET
        if (s := signal_for(sym, closes_by_symbol.get(sym, ()))) is not None
    ]
    return sorted(out, key=lambda s: -abs(s.rsi - 50.0))
