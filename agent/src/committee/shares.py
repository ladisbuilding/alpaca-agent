"""Share positions: sizing, and the risk model that makes them gateable.

⚠️ **A share position is NOT defined-risk, and this module refuses to pretend otherwise.**

Every option structure the committee trades has a long wing that caps the loss arithmetically,
which is what `verify_defined_risk` re-derives from leg geometry. A share position has no such
wing. Long stock can go to zero; short stock is unbounded. The honest description is a
**modelled** bound, not a guaranteed one, and the naming here keeps that distinction visible
rather than laundering it through a gate that means something stricter.

Why allow them at all: the two edges that actually measured out — RSI(2) reversion on
bond/international ETFs and the small-cap gap-and-go — are share strategies. Forcing them into
options would pay the options spread twice to acquire a stock-like exposure, which is how the
ORB edge died ($3.85 of edge against $4.00 of friction).

**The bound is measured, not assumed.** Per symbol, from its own realised history:

    stress_move = max(STRESS_SIGMAS * sigma, worst observed adverse session)

Over 2024-01 → 2026-08 the worst single session in the ETF basket was EFA at −6.60%, which is
6.7 of its own sigmas; IWM's worst was 4.8 sigma and TLT's 3.9. `STRESS_SIGMAS = 8` therefore
sits beyond every adverse session any of these names actually delivered, and the `max()` keeps
it honest for a symbol whose realised tail is fatter than its sigma implies.

⚠️ This is a bound on ORDINARY adverse moves. It does NOT cover a gap through the model — a
halt-and-reopen, an issuer event, a 1987. Position sizing is the only real protection there,
which is why `NOTIONAL_CAP_PCT` bounds gross exposure independently of the risk model.
"""

from __future__ import annotations

import statistics
from datetime import date
from typing import Sequence

from .gates import Proposal, ShareLeg, Side

# Beyond every adverse session observed in the basket over ~2.6 years (worst was 6.7 sigma).
STRESS_SIGMAS = 8.0
# An independent ceiling on gross exposure, because the risk model cannot see a gap through it.
NOTIONAL_CAP_PCT = 0.25
MIN_SESSIONS = 60  # below this, sigma is not a measurement


def measure_stress(closes: Sequence[float]) -> tuple[float, float] | None:
    """(sigma, stress_move) from realised history, or None if there is not enough of it."""
    if len(closes) < MIN_SESSIONS + 1:
        return None
    rets = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes)) if closes[i - 1]]
    if len(rets) < MIN_SESSIONS:
        return None
    sigma = statistics.pstdev(rets)
    worst = abs(min(rets))
    return sigma, max(STRESS_SIGMAS * sigma, worst)


def build_proposal(leg: ShareLeg, strategy: str, sigma: float) -> Proposal:
    """Wrap a share leg as a Proposal so the SAME gates run on it.

    Reusing Proposal rather than inventing a parallel path is deliberate: concentration,
    the daily loss limit, dedup, position count and buying power all apply identically to a
    share position, and a second code path would drift out of step with them.
    """
    return Proposal(
        underlying=leg.symbol,
        strategy=strategy,
        legs=(),
        max_loss=leg.modelled_max_loss,
        max_profit=leg.modelled_max_loss,  # symmetric; no defined target on a 1-day hold
        net_credit=0.0,  # shares are neither a credit nor a debit structure
        bid_ask_pct=0.0,
        share=leg,
    )


def size_to_risk(
    symbol: str,
    strategy: str,
    side: Side,
    ref_price: float,
    closes: Sequence[float],
    *,
    risk_budget: float,
    equity: float,
    exit_on: date,
) -> Proposal | None:
    """Largest position whose MODELLED loss fits the risk budget and the notional cap.

    Sizing to risk rather than to a fixed dollar amount means a quiet bond ETF takes a larger
    position than a volatile small-cap one for the same downside — the exposure follows the
    measurement instead of a round number chosen by hand.
    """
    measured = measure_stress(closes)
    if not measured or ref_price <= 0:
        return None
    sigma, stress = measured
    if stress <= 0:
        return None

    by_risk = risk_budget / (ref_price * stress)
    by_notional = (equity * NOTIONAL_CAP_PCT) / ref_price
    qty = int(min(by_risk, by_notional))
    if qty < 1:
        return None
    return build_proposal(ShareLeg(symbol, side, qty, ref_price, stress, exit_on), strategy, sigma)
