"""Candidate generation — the deterministic strategy the committee adjudicates.

The hackathon brief asks for a "clear, testable trading strategy". That is this module:
explicit rules, no model in the loop, unit-testable against a fixed chain. The LLM agents
argue about which of these candidates to take and at what size; they never conjure a
structure of their own.

Two sleeves, per the design note in docs/ARCHITECTURE.md:

  income      — defined-risk short premium (iron condors, credit verticals) at a target
                short delta. Theta is the most dependable edge over a one-week window.
  directional — small, capped debit verticals. These exist so the Bull and Bear have
                something real to disagree about; a committee with nothing to argue about
                produces a debate that reads as decorative.

Every builder returns a `Proposal` or None. Returning None is normal and expected — a
chain that cannot produce a sound structure should produce no structure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

from .chain import Contract, FillAssumption, LiquidityFilter, select_by_delta, select_wing, usable
from .gates import CONTRACT_SIZE, Leg, Proposal, Right, Side


@dataclass(frozen=True)
class IncomeConfig:
    short_delta: float = 0.16  # magnitude; sign is applied per side
    wing_width: float = 5.0  # dollars
    # ⚠️ min_dte was 1, which walked straight into the assignment trap the Bear identified:
    # "~10% chance of closing 753-758 → assignment of $75,800 SPY on a $100k book, worthless
    # wing. 'Defined risk' ends at 4pm." A short leg finishing ITM is assigned, and the long
    # wing does not help overnight. Never enter 0-1 DTE.
    min_dte: int = 2
    max_dte: int = 9
    qty: int = 1
    fill: FillAssumption = FillAssumption.CONSERVATIVE


@dataclass(frozen=True)
class DirectionalConfig:
    long_delta: float = 0.40
    short_delta: float = 0.25
    # Expiration should run roughly 2-3x the expected holding period. Holding 2-3 days means
    # 6-15 DTE; anything shorter is bought gamma you have to be right about immediately.
    min_dte: int = 5
    max_dte: int = 15
    qty: int = 1
    fill: FillAssumption = FillAssumption.CONSERVATIVE


@dataclass(frozen=True)
class CalendarConfig:
    """Sell the near expiry, buy the far one at the same strike.

    The canonical low-IV structure: it profits from the near leg decaying faster than the far
    leg, and from volatility expanding off a low base. Max loss is the debit paid, so it is
    defined risk by construction — and unlike a condor it does not need premium to be rich,
    which is the whole reason it belongs in this book.
    """

    target_delta: float = 0.50  # at the money, where the decay differential is largest
    near_min_dte: int = 2  # never the 0-1 DTE assignment trap
    near_max_dte: int = 9
    far_min_gap: int = 5  # the far leg must be meaningfully longer-dated
    qty: int = 1
    fill: FillAssumption = FillAssumption.CONSERVATIVE


def _structure_spread_pct(legs: Sequence[Contract], net_mid: float) -> float:
    """Total round-trip spread across every leg, as a fraction of the structure's mid value.

    Uses the sum of leg spreads because you cross all of them to get in. Infinite when the
    structure has no mid value to speak of, which the WIDE_SPREAD gate then rejects.
    """
    total_spread = sum(c.spread for c in legs)
    return float("inf") if abs(net_mid) < 1e-9 else total_spread / abs(net_mid)


def build_iron_condor(
    contracts: Sequence[Contract],
    expiry: date,
    config: IncomeConfig,
    liquidity: LiquidityFilter | None = None,
) -> Proposal | None:
    """Short put + short call at ±`short_delta`, each protected by a wing `wing_width` out.

    Max loss is the widest single side less the credit — a condor with non-overlapping
    shorts can only finish in the money on one side. `gates.verify_defined_risk` re-derives
    this independently, so a mistake here is caught rather than trusted.
    """
    liquidity = liquidity or LiquidityFilter()
    pool = usable(contracts, liquidity)

    short_put = select_by_delta(pool, Right.PUT, expiry, -abs(config.short_delta))
    short_call = select_by_delta(pool, Right.CALL, expiry, abs(config.short_delta))
    if not short_put or not short_call:
        return None
    if short_put.strike >= short_call.strike:
        return None  # inverted — not a condor

    long_put = select_wing(pool, Right.PUT, expiry, short_put.strike, config.wing_width)
    long_call = select_wing(pool, Right.CALL, expiry, short_call.strike, config.wing_width)
    if not long_put or not long_call:
        return None

    q = config.qty
    credit_per_share = (
        short_put.price_to_sell(config.fill)
        + short_call.price_to_sell(config.fill)
        - long_put.price_to_buy(config.fill)
        - long_call.price_to_buy(config.fill)
    )
    if credit_per_share <= 0:
        return None  # structure pays nothing at a realistic fill

    net_credit = credit_per_share * CONTRACT_SIZE * q
    put_width = short_put.strike - long_put.strike
    call_width = long_call.strike - short_call.strike
    max_loss = max(put_width, call_width) * CONTRACT_SIZE * q - net_credit
    if max_loss <= 0:
        return None  # credit exceeds width: a mispriced or stale quote, not free money

    mid_credit = (
        short_put.mid + short_call.mid - long_put.mid - long_call.mid
    ) * CONTRACT_SIZE * q

    return Proposal(
        underlying=short_put.underlying,
        strategy="iron_condor",
        legs=(
            Leg(short_put.symbol, Side.SELL, q, Right.PUT, short_put.strike, expiry),
            Leg(long_put.symbol, Side.BUY, q, Right.PUT, long_put.strike, expiry),
            Leg(short_call.symbol, Side.SELL, q, Right.CALL, short_call.strike, expiry),
            Leg(long_call.symbol, Side.BUY, q, Right.CALL, long_call.strike, expiry),
        ),
        max_loss=max_loss,
        max_profit=net_credit,
        net_credit=net_credit,
        bid_ask_pct=_structure_spread_pct(
            [short_put, long_put, short_call, long_call], mid_credit / (CONTRACT_SIZE * q)
        ),
    )


def build_credit_vertical(
    contracts: Sequence[Contract],
    expiry: date,
    right: Right,
    config: IncomeConfig,
    liquidity: LiquidityFilter | None = None,
) -> Proposal | None:
    """One side of a condor. PUT side expresses a bullish-to-neutral view, CALL side bearish."""
    liquidity = liquidity or LiquidityFilter()
    pool = usable(contracts, liquidity)

    target = -abs(config.short_delta) if right is Right.PUT else abs(config.short_delta)
    short = select_by_delta(pool, right, expiry, target)
    if not short:
        return None
    long = select_wing(pool, right, expiry, short.strike, config.wing_width)
    if not long:
        return None

    q = config.qty
    credit_per_share = short.price_to_sell(config.fill) - long.price_to_buy(config.fill)
    if credit_per_share <= 0:
        return None

    net_credit = credit_per_share * CONTRACT_SIZE * q
    width = abs(short.strike - long.strike)
    max_loss = width * CONTRACT_SIZE * q - net_credit
    if max_loss <= 0:
        return None

    name = "put_credit_spread" if right is Right.PUT else "call_credit_spread"
    return Proposal(
        underlying=short.underlying,
        strategy=name,
        legs=(
            Leg(short.symbol, Side.SELL, q, right, short.strike, expiry),
            Leg(long.symbol, Side.BUY, q, right, long.strike, expiry),
        ),
        max_loss=max_loss,
        max_profit=net_credit,
        net_credit=net_credit,
        bid_ask_pct=_structure_spread_pct([short, long], short.mid - long.mid),
    )


def build_debit_vertical(
    contracts: Sequence[Contract],
    expiry: date,
    right: Right,
    config: DirectionalConfig,
    liquidity: LiquidityFilter | None = None,
) -> Proposal | None:
    """The directional sleeve: buy the nearer-the-money strike, sell the further one.

    Max loss is the debit paid, so it is defined by construction. Deliberately small —
    this sleeve exists to give the committee a genuine disagreement to resolve, not to
    carry the P&L.
    """
    liquidity = liquidity or LiquidityFilter()
    pool = usable(contracts, liquidity)

    sign = -1.0 if right is Right.PUT else 1.0
    long_leg = select_by_delta(pool, right, expiry, sign * abs(config.long_delta))
    short_leg = select_by_delta(pool, right, expiry, sign * abs(config.short_delta))
    if not long_leg or not short_leg or long_leg.symbol == short_leg.symbol:
        return None

    # the short must be further out of the money than the long, or this is not a debit spread
    if right is Right.CALL and short_leg.strike <= long_leg.strike:
        return None
    if right is Right.PUT and short_leg.strike >= long_leg.strike:
        return None

    q = config.qty
    debit_per_share = long_leg.price_to_buy(config.fill) - short_leg.price_to_sell(config.fill)
    if debit_per_share <= 0:
        return None  # a credit here means the quotes are stale

    debit = debit_per_share * CONTRACT_SIZE * q
    width = abs(long_leg.strike - short_leg.strike)
    max_profit = width * CONTRACT_SIZE * q - debit
    if max_profit <= 0:
        return None  # paying more than the spread can ever return

    name = "call_debit_spread" if right is Right.CALL else "put_debit_spread"
    return Proposal(
        underlying=long_leg.underlying,
        strategy=name,
        legs=(
            Leg(long_leg.symbol, Side.BUY, q, right, long_leg.strike, expiry),
            Leg(short_leg.symbol, Side.SELL, q, right, short_leg.strike, expiry),
        ),
        max_loss=debit,
        max_profit=max_profit,
        net_credit=-debit,
        bid_ask_pct=_structure_spread_pct([long_leg, short_leg], long_leg.mid - short_leg.mid),
    )


def build_calendar(
    contracts: Sequence[Contract],
    near_expiry: date,
    far_expiry: date,
    right: Right,
    config: CalendarConfig,
    liquidity: LiquidityFilter | None = None,
) -> Proposal | None:
    """Sell the near expiry, buy the far one, same strike.

    Max loss is the debit paid. Note the structure's `expiry` will read as the FAR leg, which
    is correct for the dedup fingerprint but is not when the trade resolves — the near leg
    expiring is the event that matters.
    """
    liquidity = liquidity or LiquidityFilter()
    pool = usable(contracts, liquidity)
    if near_expiry >= far_expiry:
        return None
    if (far_expiry - near_expiry).days < config.far_min_gap:
        return None

    sign = -1.0 if right is Right.PUT else 1.0
    near = select_by_delta(pool, right, near_expiry, sign * abs(config.target_delta))
    if not near:
        return None
    # The far leg must be the SAME strike — that is what makes it a calendar rather than a
    # diagonal, and what keeps the risk profile symmetric.
    far = next(
        (c for c in pool if c.right is right and c.expiry == far_expiry and c.strike == near.strike),
        None,
    )
    if not far:
        return None

    q = config.qty
    debit_per_share = far.price_to_buy(config.fill) - near.price_to_sell(config.fill)
    if debit_per_share <= 0:
        return None  # the far leg is not dearer than the near one: inverted term structure

    debit = debit_per_share * CONTRACT_SIZE * q
    # A calendar's upside is not a fixed geometric quantity the way a vertical's is — it
    # depends on where the underlying sits at near expiry and on the far leg's remaining
    # value. Estimating it as the debit is deliberately conservative: it means the credit
    # and profit-quality gates judge the structure on what it certainly risks rather than on
    # a modelled best case.
    return Proposal(
        underlying=near.underlying,
        strategy=f"calendar_{right.value}",
        legs=(
            Leg(near.symbol, Side.SELL, q, right, near.strike, near_expiry),
            Leg(far.symbol, Side.BUY, q, right, far.strike, far_expiry),
        ),
        max_loss=debit,
        max_profit=debit,  # conservative placeholder, see above
        net_credit=-debit,
        bid_ask_pct=_structure_spread_pct([near, far], far.mid - near.mid),
    )


def size_for_risk(
    build,
    risk_budget: float,
    *,
    max_qty: int = 10,
) -> Proposal | None:
    """Scale a structure to the risk budget instead of trading a hardcoded quantity.

    Both winning condors so far made $21 and $12 — not because the edge was small, but
    because `qty=1` with $5 wings caps max profit near $60 and we were using $400 of a $1,000
    per-trade allowance. The measured edge was fine; the position was a rounding error.

    `build` is a callable taking qty and returning a Proposal (or None). A defined-risk
    structure's max loss is linear in quantity — (width x 100 - credit) x qty — so the size is
    solved at qty=1 and applied directly rather than searched for.

    The deterministic gates remain the ceiling: TRADE_TOO_LARGE, PORTFOLIO_RISK_CAP and
    INSUFFICIENT_BUYING_POWER all re-check the result. This decides intent; they decide what
    is permitted.
    """
    one = build(1)
    if one is None or one.max_loss <= 0:
        return one

    qty = int(risk_budget // one.max_loss)
    if qty <= 1:
        return one  # the budget does not stretch past a single contract
    return build(min(qty, max_qty)) or one
