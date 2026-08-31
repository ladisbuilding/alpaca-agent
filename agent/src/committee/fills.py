"""Record what we ACTUALLY paid, against what the market was quoting when we ordered.

⚠️ **This is the single most important measurement on the project, and it did not exist.**

Four strategies have now been tested honestly here and all four died the same death:

    ORB            edge $3.85/contract vs friction $4.00
    RSI(2)         negative in 9 of 11 years
    gap-and-go     +0.088R at a MID fill, +0.001R once you CROSS the spread
    income sleeve  -$26.56/condor at 2-9 DTE, crossing all four legs

Every one turned on the same unknown: **do we cross the spread, or do we get price
improvement?** A backtest cannot answer it — it can only assume. And paper trading cannot
answer it either, because paper fills instantly at the quote, which is the exact fiction in
question. What CAN answer it is recording, per order, the quote at submission and the price
actually filled.

⭐ The one real data point so far is n=2: two condors closed +$21 and +$12 NET, close to
IWM's GROSS backtest figure — hinting the limit orders got price improvement rather than
crossing. **n=2 is not evidence.** This module exists to turn that into a sample.

The number that decides everything downstream:

    slippage_fraction = (fill - mid) / (half-spread)        for a BUY

      0.0  filled at the mid          — the optimistic backtests were right
      1.0  filled at the ask          — crossed the spread; the edge is zero
     >1.0  worse than the quoted ask  — the pessimistic case
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FillRecord:
    """One leg: what was quoted when we ordered, and what we actually got."""

    symbol: str
    side: str  # "buy" | "sell"
    qty: int
    bid: float
    ask: float
    fill_price: float

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def half_spread(self) -> float:
        return (self.ask - self.bid) / 2.0

    @property
    def slippage_fraction(self) -> float | None:
        """0 = filled at mid, 1 = crossed to the far side, >1 = worse than the quote.

        Signed so that POSITIVE always means "paid away", for a buy and a sell alike —
        otherwise the two sides cancel and a book that is bleeding looks flat.
        """
        hs = self.half_spread
        if hs <= 0:
            return None
        if self.side == "buy":
            return (self.fill_price - self.mid) / hs
        return (self.mid - self.fill_price) / hs

    @property
    def dollars_paid_away(self) -> float:
        f = self.slippage_fraction
        return 0.0 if f is None else f * self.half_spread * self.qty * 100

    def describe(self) -> str:
        f = self.slippage_fraction
        where = "unquoted" if f is None else (
            "AT MID" if f <= 0.1 else
            "inside" if f < 0.9 else
            "CROSSED" if f <= 1.1 else
            "WORSE THAN QUOTE"
        )
        return (
            f"{self.side} {self.qty} {self.symbol} @ {self.fill_price:.2f} "
            f"(bid {self.bid:.2f} / ask {self.ask:.2f}, mid {self.mid:.2f}) "
            f"-> {f if f is None else round(f, 2)} of the half-spread [{where}], "
            f"${self.dollars_paid_away:+,.2f}"
        )


@dataclass
class FillReport:
    fills: list[FillRecord] = field(default_factory=list)

    def add(self, fill: FillRecord) -> None:
        self.fills.append(fill)

    @property
    def measurable(self) -> list[FillRecord]:
        return [f for f in self.fills if f.slippage_fraction is not None]

    def summary(self) -> dict[str, Any]:
        """The verdict, in the terms the decision was framed in.

        ⚠️ Deliberately reports the MEDIAN rather than the mean: one leg filled far outside a
        stale quote would otherwise dominate, and the question is what happens typically.
        """
        xs = sorted(f.slippage_fraction for f in self.measurable)  # type: ignore[misc]
        if not xs:
            return {"n": 0, "verdict": "no measurable fills yet"}
        median = xs[len(xs) // 2]
        return {
            "n": len(xs),
            "median_slippage_fraction": round(median, 3),
            "at_or_better_than_mid": sum(1 for x in xs if x <= 0.1) / len(xs),
            "crossed_or_worse": sum(1 for x in xs if x >= 0.9) / len(xs),
            "total_paid_away": round(sum(f.dollars_paid_away for f in self.measurable), 2),
            "verdict": (
                "price improvement — the mid-fill backtests apply"
                if median < 0.5
                else "crossing the spread — the edge is zero, stop"
            ),
        }
