"""Regime detection and the calendar structure.

The regime read exists because five live debates were killed on the same point: the strategy
assumed premium was rich when it was not. Deciding whether the premise holds is arithmetic,
so it must be tested like arithmetic.
"""

from datetime import date, timedelta

import pytest

from committee.chain import Contract, LiquidityFilter
from committee.gates import Right, Side, evaluate, has_uncovered_short
from committee.market import realized_vol
from committee.regime import CHEAP_BELOW, RICH_ABOVE, Regime, classify
from committee.strategy import CalendarConfig, build_calendar

NEAR = date(2026, 8, 27)
FAR = date(2026, 9, 3)


# ── regime ─────────────────────────────────────────────────────────────────────────


def test_rich_premium_says_sell():
    r = classify(0.30, 0.20, "XYZ")
    assert r.regime is Regime.PREMIUM_RICH
    assert r.sleeve == "income"
    assert "RICH" in r.explain()


def test_cheap_premium_says_buy():
    """The live QQQ read: IV 22.8% vs realized 21.6% = 1.06x."""
    r = classify(0.228, 0.216, "QQQ")
    assert r.regime is Regime.PREMIUM_CHEAP
    assert r.sleeve == "long_premium"
    assert "calendars" in r.explain()


def test_the_middle_says_stand_down():
    """The live SPY read: 1.20x. Not paid to sell, not obviously cheap to buy."""
    r = classify(0.146, 0.122, "SPY")
    assert r.regime is Regime.NO_EDGE
    assert r.sleeve == "none"
    assert "NO CLEAR EDGE" in r.explain()


@pytest.mark.parametrize("iv,rv", [(None, 0.2), (0.2, None), (0.2, 0.0)])
def test_missing_inputs_are_unknown_not_a_guess(iv, rv):
    """A missing input must never resolve to a tradeable verdict — a broken realized-vol
    call once made every underlying read 'unknown', which looked like a market condition
    rather than a bug."""
    r = classify(iv, rv, "X")
    assert r.regime is Regime.UNKNOWN
    assert r.sleeve == "none"


def test_thresholds_are_exclusive_at_the_boundary():
    assert classify(RICH_ABOVE * 0.2, 0.2).regime is Regime.NO_EDGE  # exactly 1.30 is not rich
    assert classify(CHEAP_BELOW * 0.2, 0.2).regime is Regime.NO_EDGE  # exactly 1.10 is not cheap


# ── realized vol ───────────────────────────────────────────────────────────────────


def test_realized_vol_is_annualised():
    """A series moving a steady 1%/day should annualise near 1% * sqrt(252)."""
    closes = [100.0]
    for i in range(31):
        closes.append(closes[-1] * (1.01 if i % 2 == 0 else 1 / 1.01))
    rv = realized_vol(closes, sessions=30)
    assert rv is not None
    assert 0.10 < rv < 0.25


def test_realized_vol_uses_a_fixed_window():
    """A scout allowed to choose its lookback picks a flattering one: a live nomination cited
    0.47%/day from 10 sessions when 30 sessions gave 0.78%."""
    calm = [100.0 + i * 0.01 for i in range(40)]
    shocked = calm[:20] + [80.0, 100.0, 85.0] + calm[23:]
    assert realized_vol(shocked, 30) > realized_vol(calm, 30)


def test_too_few_closes_returns_none_not_zero():
    assert realized_vol([100.0]) is None
    assert realized_vol([]) is None


# ── calendar ───────────────────────────────────────────────────────────────────────


def cal_chain() -> list[Contract]:
    """Two expiries at the same strikes; the far leg is dearer, as term structure implies."""
    out = []
    for expiry, mult in ((NEAR, 1.0), (FAR, 1.8)):
        for strike in range(290, 311):
            moneyness = (strike - 300) / 300
            delta = max(0.01, min(0.99, 0.5 - moneyness * 22))
            mid = max(0.10, (4.0 - abs(strike - 300) * 0.30) * mult)
            out.append(
                Contract(
                    symbol=f"IWM{expiry:%y%m%d}C{int(strike*1000):08d}",
                    underlying="IWM",
                    expiry=expiry,
                    right=Right.CALL,
                    strike=float(strike),
                    bid=round(mid - 0.04, 2),
                    ask=round(mid + 0.04, 2),
                    delta=round(delta, 4),
                    implied_volatility=0.18,
                )
            )
    return out


def test_calendar_sells_near_and_buys_far_at_the_same_strike():
    p = build_calendar(cal_chain(), NEAR, FAR, Right.CALL, CalendarConfig())
    assert p is not None
    near = next(l for l in p.legs if l.side is Side.SELL)
    far = next(l for l in p.legs if l.side is Side.BUY)
    assert near.expiry == NEAR and far.expiry == FAR
    assert near.strike == far.strike, "same strike is what makes it a calendar, not a diagonal"


def test_calendar_max_loss_is_the_debit():
    p = build_calendar(cal_chain(), NEAR, FAR, Right.CALL, CalendarConfig())
    assert p.net_credit < 0
    assert p.max_loss == pytest.approx(-p.net_credit)
    assert not has_uncovered_short(p)


def test_calendar_needs_a_meaningful_gap_between_expiries():
    """Adjacent expiries have almost no decay differential — that is not a calendar."""
    assert build_calendar(cal_chain(), NEAR, NEAR + timedelta(days=2), Right.CALL, CalendarConfig()) is None


def test_calendar_rejects_inverted_term_structure():
    """If the near leg is dearer than the far one, there is no debit to pay and the premise
    is inverted."""
    chain = [
        c if c.expiry == NEAR else Contract(
            c.symbol, c.underlying, c.expiry, c.right, c.strike, 0.05, 0.09, c.delta, c.implied_volatility
        )
        for c in cal_chain()
    ]
    assert build_calendar(chain, NEAR, FAR, Right.CALL, CalendarConfig()) is None


def test_calendar_survives_the_gates():
    from datetime import datetime, timezone

    from committee.gates import PortfolioState, RiskConfig

    p = build_calendar(cal_chain(), NEAR, FAR, Right.CALL, CalendarConfig())
    portfolio = PortfolioState(
        equity=100_000.0, cash=100_000.0, buying_power=100_000.0, realized_pnl_today=0.0
    )
    now = datetime(2026, 8, 25, 15, 0, tzinfo=timezone(timedelta(hours=-4)))
    result = evaluate(p, portfolio, RiskConfig(), now)
    assert result.approved, f"blocked by {result.blocked_by}: {result.reasons}"
