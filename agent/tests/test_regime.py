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
from committee.strategy import CalendarConfig, build_calendar
from committee.regime import (
    BUYER_EDGE_ABOVE,
    FAIR_BREACH,
    MIN_WINDOWS,
    SELLER_EDGE_BELOW,
    Regime,
    classify,
)


NEAR = date(2026, 8, 27)
FAR = date(2026, 9, 3)


# ── regime, measured at the horizon actually traded ────────────────────────────────
#
# This module was wrong once: it compared ANNUALISED IV against 30-DAY realised vol, which
# is the right test for a multi-week structure and the wrong one for a 2-DTE structure. It
# reported "no premium edge anywhere" and the committee correctly refused everything for two
# days. These tests pin the corrected behaviour.


def closes_where(pct_of_windows_move: float, move: float, dte: int = 2, n: int = 90) -> list[float]:
    """Build closes so that a KNOWN fraction of `dte`-session windows move more than `move`.

    Constructed rather than simulated: the breach rate is the statistic under test, so it
    must be known by construction, not assumed from a plausible-looking price path.
    """
    big = int(n * pct_of_windows_move)
    out = [100.0]
    for i in range(n):
        # A big move every k-th step; everything else is flat, so exactly the windows
        # containing a big move breach.
        step = move * 1.5 if (big and i % max(int(n / big), 1) == 0) else 0.0
        out.append(out[-1] * (1 + step))
    return out


def test_an_implied_move_the_underlying_rarely_reaches_is_a_seller_edge():
    """IWM's live read: a 1.11% implied move exceeded only 22% of the time against a fair
    value near 32%."""
    # implied 2-day move at 40% IV ≈ 3.6%; build a tape that exceeds it ~10% of windows
    r = classify("IWM", atm_iv=0.40, dte=2, closes=closes_where(0.05, 0.036))
    assert r.regime is Regime.PREMIUM_RICH
    assert r.sleeve == "income"
    assert r.breach_rate < SELLER_EDGE_BELOW
    assert "RICH" in r.explain()


def test_an_implied_move_the_underlying_routinely_exceeds_is_a_buyer_edge():
    # implied 2-day move at 5% IV ≈ 0.45%; a tape that clears it most windows
    r = classify("XYZ", atm_iv=0.05, dte=2, closes=closes_where(0.60, 0.005))
    assert r.regime is Regime.PREMIUM_CHEAP
    assert r.sleeve == "long_premium"
    assert r.breach_rate > BUYER_EDGE_ABOVE
    assert "CHEAP" in r.explain()


def test_a_fairly_priced_market_stands_down():
    """QQQ's live read: breached 31% against a fair value of ~32%. Neither side is overpaid,
    so neither selling nor buying has an edge."""
    # implied 1-day move at 25.6% IV ≈ 1.6%; a tape that clears it about a third of the time
    r = classify("QQQ", atm_iv=0.256, dte=1, closes=closes_where(0.32, 0.016, dte=1))
    assert r.regime is Regime.NO_EDGE
    assert r.sleeve == "none"
    assert "FAIRLY PRICED" in r.explain()


def test_the_dte_used_for_the_implied_move_must_match_the_windows_measured():
    """The whole point of the rewrite. The same IV read at 2 DTE and at 20 DTE implies very
    different moves, and each must be compared against moves over ITS OWN horizon."""
    closes = closes_where(0.2, 0.01)
    short = classify("X", atm_iv=0.20, dte=2, closes=closes)
    long = classify("X", atm_iv=0.20, dte=20, closes=closes)
    assert short.implied_move < long.implied_move
    assert short.dte == 2 and long.dte == 20


def test_a_low_breach_rate_on_too_few_windows_is_unknown_not_an_edge():
    """A breach rate over a handful of windows is noise. Reporting it as a tradeable verdict
    is how a measurement error becomes a position."""
    r = classify("X", atm_iv=0.20, dte=2, closes=closes_where(0.1, 0.01, n=10))
    assert r.regime is Regime.UNKNOWN
    assert r.sleeve == "none"


@pytest.mark.parametrize(
    "iv,dte,closes",
    [
        (None, 2, closes_where(0.1, 0.01)),
        (0.2, None, closes_where(0.1, 0.01)),
        (0.2, 0, closes_where(0.1, 0.01)),
        (0.2, 2, []),
    ],
)
def test_missing_inputs_are_unknown_not_a_guess(iv, dte, closes):
    r = classify("X", iv, dte, closes)
    assert r.regime is Regime.UNKNOWN
    assert r.sleeve == "none"


def test_the_read_reports_its_own_sample_size():
    """Every verdict carries how many windows it rests on, so a reader can judge it."""
    r = classify("X", atm_iv=0.20, dte=2, closes=closes_where(0.1, 0.01))
    assert r.windows >= MIN_WINDOWS
    assert str(r.windows) in r.explain()
    assert f"{FAIR_BREACH:.0%}" in r.explain()


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
