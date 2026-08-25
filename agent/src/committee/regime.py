"""Which edge exists today.

Deterministic, no model in the loop — the same rule as the gates and the audit. The
committee's job is to argue about *candidates*; deciding whether the strategy's premise even
holds is arithmetic, and arithmetic should not be negotiable.

The measurement that matters for an options book is **IV/RV**: implied volatility on the
strikes we would actually trade, against realized volatility over a fixed window.

  IV/RV > 1.30   premium is rich       → SELL premium (condors, credit verticals)
  1.10–1.30      no clear edge          → stand down, or take only high-conviction directional
  IV/RV < 1.10   premium is cheap      → BUY premium (debit verticals, calendars)

⚠️ Both inputs have to be measured honestly or this is worse than nothing:

* **IV must come from tradable strikes only.** A chain-wide median is polluted by deep-ITM
  strikes trading 1–13 contracts, which inflated SPY's apparent IV to 22–24% when the strikes
  we would sell priced at 13–16%. Scouts nominated on a "3x IV/RV" premise that did not exist
  and the Bear killed all five live debates on exactly that point.
* **RV must use a fixed window.** A scout allowed to choose its own lookback will choose a
  flattering one: a live nomination cited 0.47%/day from a 10-session window when the
  30-session figure was 0.78%/day.

Measured 2026-08-25 with both fixed: SPY 1.19x, QQQ 1.04x, IWM 1.23x. No variance premium
anywhere — which is why an agent that refused everything was reading the market correctly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# Selling premium needs to be paid for the tail. Below this the credit does not compensate
# for the risk of the move actually happening, because implied is barely above realized.
RICH_ABOVE = 1.30
# Below this, options are cheap relative to how much the underlying actually moves, which is
# the condition long premium and calendars are designed for.
CHEAP_BELOW = 1.10


class Regime(str, Enum):
    PREMIUM_RICH = "premium_rich"
    NO_EDGE = "no_edge"
    PREMIUM_CHEAP = "premium_cheap"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RegimeRead:
    underlying: str
    regime: Regime
    iv: float | None
    realized: float | None
    ratio: float | None

    @property
    def sleeve(self) -> str:
        """Which sleeve the scouts should hunt in."""
        return {
            Regime.PREMIUM_RICH: "income",
            Regime.PREMIUM_CHEAP: "long_premium",
            Regime.NO_EDGE: "none",
            Regime.UNKNOWN: "none",
        }[self.regime]

    def explain(self) -> str:
        if self.ratio is None:
            return f"{self.underlying}: regime unknown (IV or realized vol unavailable)"
        base = (
            f"{self.underlying}: IV {self.iv:.1%} vs realized {self.realized:.1%} "
            f"= {self.ratio:.2f}x"
        )
        if self.regime is Regime.PREMIUM_RICH:
            return f"{base} — premium is RICH. Selling defined-risk premium is justified."
        if self.regime is Regime.PREMIUM_CHEAP:
            return (
                f"{base} — premium is CHEAP. Selling it is not paid for; buy premium instead "
                "(debit verticals, calendars)."
            )
        return (
            f"{base} — NO CLEAR EDGE either way. Selling is not paid for and buying is not "
            "obviously cheap. Standing down is the correct default."
        )


def classify(iv: float | None, realized: float | None, underlying: str = "?") -> RegimeRead:
    if not iv or not realized or realized <= 0:
        return RegimeRead(underlying, Regime.UNKNOWN, iv, realized, None)
    ratio = iv / realized
    if ratio > RICH_ABOVE:
        regime = Regime.PREMIUM_RICH
    elif ratio < CHEAP_BELOW:
        regime = Regime.PREMIUM_CHEAP
    else:
        regime = Regime.NO_EDGE
    return RegimeRead(underlying, regime, iv, realized, ratio)
