"""Share positions: sizing, the modelled risk bound, and the gates that must not be bypassed.

The dangerous failure this file guards is a share position slipping through the OPTION risk
path — has_uncovered_short() sees no legs and returns False, verify_defined_risk() returns
None, and the position is then sized off a number nothing ever checked.
"""

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from committee.gates import (  # noqa: E402
    OpenPosition,
    PortfolioState,
    Proposal,
    RiskConfig,
    ShareLeg,
    Side,
    evaluate,
    verify_share_risk,
)
from committee.reversion import BASKET, rsi, scan, signal_for  # noqa: E402
from committee.shares import build_proposal, measure_stress, size_to_risk  # noqa: E402

EXIT = date(2026, 9, 2)
NOW = datetime(2026, 9, 1, 15, 0, tzinfo=timezone.utc)  # 11:00 ET, mid-session


def book(equity: float = 100_000.0) -> PortfolioState:
    return PortfolioState(equity=equity, cash=equity, buying_power=equity * 4,
                          realized_pnl_today=0.0, open_positions=())


def series(n: int = 300, drift: float = 0.0, vol: float = 0.01) -> list[float]:
    """Deterministic pseudo-random walk — no Math.random equivalent in a test."""
    out = [100.0]
    for i in range(n):
        step = ((i * 7919) % 1000) / 1000.0 - 0.5
        out.append(out[-1] * (1 + drift + vol * step))
    return out


# ── the risk model ────────────────────────────────────────────────────────────────

def test_stress_bound_exceeds_every_observed_session():
    closes = series()
    sigma, stress = measure_stress(closes)
    rets = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]
    assert stress >= abs(min(rets))  # never below what actually happened
    assert stress >= 8.0 * sigma - 1e-12


def test_measure_stress_refuses_a_short_history():
    assert measure_stress([100.0] * 10) is None


def test_sizing_respects_the_risk_budget():
    closes = series()
    p = size_to_risk("EFA", "rsi2_reversion", Side.BUY, closes[-1], closes,
                     risk_budget=2000.0, equity=100_000.0, exit_on=EXIT)
    assert p is not None and p.is_share
    assert p.max_loss <= 2000.0 + 1e-6
    assert p.max_loss == pytest.approx(verify_share_risk(p))


def test_a_quiet_asset_gets_a_bigger_position_than_a_volatile_one():
    """Sizing follows the measurement, not a round number chosen by hand.

    Equity is deliberately large here so the NOTIONAL cap stays slack — at $100k both
    positions clamp to the 25% ceiling and come out equal, which hides the property under
    test rather than disproving it.
    """
    big = 2_000_000.0
    quiet = size_to_risk("HYG", "rsi2_reversion", Side.BUY, series(vol=0.002)[-1],
                         series(vol=0.002), risk_budget=2000.0, equity=big, exit_on=EXIT)
    loud = size_to_risk("IWM", "rsi2_reversion", Side.BUY, series(vol=0.03)[-1],
                        series(vol=0.03), risk_budget=2000.0, equity=big, exit_on=EXIT)
    assert quiet.share.notional > loud.share.notional
    # notional = risk_budget / stress, so the ordering is exactly the stress ordering
    assert quiet.share.stress_move < loud.share.stress_move


def test_the_notional_cap_binds_before_the_risk_model_on_a_quiet_asset():
    """The case above, at a REAL account size — here the cap is what actually protects us."""
    p = size_to_risk("HYG", "rsi2_reversion", Side.BUY, series(vol=0.002)[-1],
                     series(vol=0.002), risk_budget=2000.0, equity=100_000.0, exit_on=EXIT)
    assert p.share.notional <= 25_000.0 + 1e-6
    assert p.max_loss < 2000.0  # risk budget was never the binding constraint


# ── the gates ─────────────────────────────────────────────────────────────────────

def test_a_share_position_cannot_understate_its_own_risk():
    """THE test. An under-reported max_loss must be caught, not sized off."""
    leg = ShareLeg("EFA", Side.BUY, qty=300, ref_price=80.0, stress_move=0.08, exit_on=EXIT)
    honest = build_proposal(leg, "rsi2_reversion", sigma=0.01)
    assert honest.max_loss == pytest.approx(300 * 80.0 * 0.08)

    lying = Proposal(underlying="EFA", strategy="rsi2_reversion", legs=(),
                     max_loss=1.0,  # claims a dollar of risk on a $24k position
                     max_profit=1.0, net_credit=0.0, share=leg)
    r = evaluate(lying, book(), RiskConfig(), NOW)
    assert not r.approved and "MISREPORTED_RISK" in r.blocked_by


def test_a_proposal_must_be_shares_or_options_never_neither():
    """A legless, shareless proposal is one no gate can verify — refuse it at construction."""
    with pytest.raises(ValueError):
        Proposal(underlying="EFA", strategy="x", legs=(), max_loss=100.0,
                 max_profit=100.0, net_credit=0.0)


def test_a_share_leg_must_match_the_underlying_it_claims():
    leg = ShareLeg("EEM", Side.BUY, qty=100, ref_price=50.0, stress_move=0.08, exit_on=EXIT)
    p = Proposal(underlying="EFA", strategy="rsi2_reversion", legs=(),
                 max_loss=leg.modelled_max_loss, max_profit=leg.modelled_max_loss,
                 net_credit=0.0, share=leg)
    r = evaluate(p, book(), RiskConfig(), NOW)
    assert not r.approved and "MISREPORTED_RISK" in r.blocked_by


def test_notional_is_capped_independently_of_the_risk_model():
    """A very quiet asset would otherwise size to an enormous position on a small stress."""
    leg = ShareLeg("HYG", Side.BUY, qty=100_000, ref_price=80.0, stress_move=0.005, exit_on=EXIT)
    p = build_proposal(leg, "rsi2_reversion", sigma=0.001)
    r = evaluate(p, book(), RiskConfig(), NOW)
    assert not r.approved and "NOTIONAL_TOO_LARGE" in r.blocked_by


def test_an_honest_share_position_passes():
    closes = series()
    p = size_to_risk("EFA", "rsi2_reversion", Side.BUY, closes[-1], closes,
                     risk_budget=1500.0, equity=100_000.0, exit_on=EXIT)
    r = evaluate(p, book(), RiskConfig(), NOW)
    assert r.approved, r.blocked_by


def test_shares_still_face_the_generic_gates():
    """Reusing Proposal means concentration, daily loss and the rest apply unchanged."""
    closes = series()
    p = size_to_risk("EFA", "rsi2_reversion", Side.BUY, closes[-1], closes,
                     risk_budget=1500.0, equity=100_000.0, exit_on=EXIT)
    down = PortfolioState(equity=100_000.0, cash=100_000.0, buying_power=400_000.0,
                          realized_pnl_today=-99_000.0, open_positions=())
    r = evaluate(p, down, RiskConfig(), NOW)
    assert not r.approved and "DAILY_LOSS_LIMIT" in r.blocked_by


# ── the signal ────────────────────────────────────────────────────────────────────

def test_a_flat_series_is_neutral_not_overbought():
    """A constant price has no gains AND no losses. The usual losses==0 -> 100 shortcut
    reports maximum overbought on a price that never moved, and fired a short signal."""
    assert rsi([100.0] * 21) == 50.0
    assert scan({"TLT": [100.0] * 21}) == []


def test_oversold_goes_long_and_overbought_goes_short():
    falling = [100.0 * (0.99 ** i) for i in range(21)]
    rising = [100.0 * (1.01 ** i) for i in range(21)]
    assert signal_for("EFA", falling).direction == "long"
    assert signal_for("IWM", rising).direction == "short"


def test_no_signal_in_the_middle():
    assert signal_for("TLT", [100.0, 101.0, 100.5, 100.8]) is None


def test_scan_ranks_the_most_stretched_first():
    falling = [100.0 * (0.99 ** i) for i in range(21)]
    mild = [100.0, 99.0, 98.9, 98.6, 98.4, 98.39]
    out = scan({"EFA": falling, "TLT": mild})
    assert out and abs(out[0].rsi - 50) >= abs(out[-1].rsi - 50)


def test_the_basket_is_the_hypothesis_and_excludes_commodities():
    """SLV/GDX/XLU/XLE measured NEGATIVE. The universe is the claim, not a convenience."""
    for banned in ("SLV", "GDX", "XLU", "XLE", "GLD", "USO"):
        assert banned not in BASKET
    assert set(BASKET) == {"LQD", "HYG", "TLT", "IEF", "EFA", "EEM", "IWM"}


def test_signal_reads_the_last_close():
    """An off-by-one here is a wrong trade, not a crash — so it is asserted explicitly."""
    falling = [100.0 * (0.99 ** i) for i in range(21)]
    assert signal_for("EFA", falling).ref_price == pytest.approx(falling[-1])


# ── aggregate exposure ────────────────────────────────────────────────────────────

def held(symbol: str, notional: float, risk: float) -> OpenPosition:
    return OpenPosition(symbol, "rsi2_reversion", f"{symbol}|fp", risk, EXIT,
                        share_notional=notional)


def test_gross_exposure_is_capped_across_positions():
    """The per-position cap cannot bound this: quiet assets size to a large notional for a
    small modelled loss, so a basket can reach several hundred percent gross while every
    single position, and the total RISK, stay inside their limits."""
    book_ = PortfolioState(
        equity=100_000.0, cash=100_000.0, buying_power=400_000.0, realized_pnl_today=0.0,
        open_positions=tuple(held(f"S{i}", 24_000.0, 400.0) for i in range(6)),
    )
    assert book_.gross_share_notional == 144_000.0
    assert book_.deployed_risk == 2_400.0  # only 2.4% risk — the risk cap is nowhere near
    leg = ShareLeg("HYG", Side.BUY, qty=300, ref_price=80.0, stress_move=0.02, exit_on=EXIT)
    r = evaluate(build_proposal(leg, "rsi2_reversion", 0.004), book_, RiskConfig(), NOW)
    assert not r.approved and "GROSS_EXPOSURE" in r.blocked_by


def test_option_positions_do_not_count_toward_share_exposure():
    """An option structure's risk is bounded by geometry, so it carries no share notional."""
    book_ = PortfolioState(
        equity=100_000.0, cash=100_000.0, buying_power=400_000.0, realized_pnl_today=0.0,
        open_positions=(OpenPosition("QQQ", "iron_condor", "fp", 400.0, EXIT),),
    )
    assert book_.gross_share_notional == 0.0


def test_a_correlated_basket_is_summed_not_root_summed():
    """The basket's mean pairwise correlation is 0.51 and LQD/TLT/IEF sit at 0.89-0.92, so
    ~7 assets are ~1.7 independent bets. Summing max_loss is the perfectly-correlated worst
    case, which is the honest assumption here — root-summing would understate it."""
    book_ = PortfolioState(
        equity=100_000.0, cash=100_000.0, buying_power=400_000.0, realized_pnl_today=0.0,
        open_positions=tuple(held(f"S{i}", 20_000.0, 1_900.0) for i in range(5)),
    )
    assert book_.deployed_risk == 9_500.0  # summed, not sqrt(5)*1900 = 4249
    closes = series()
    p = size_to_risk("EFA", "rsi2_reversion", Side.BUY, closes[-1], closes,
                     risk_budget=1500.0, equity=100_000.0, exit_on=EXIT)
    r = evaluate(p, book_, RiskConfig(), NOW)
    assert not r.approved and "PORTFOLIO_RISK_CAP" in r.blocked_by


# ── the round trip: proposal -> record -> held position -> exit ───────────────────

from committee.cycle import _structure_dict  # noqa: E402
from committee.manage import evaluate_exit, held_positions  # noqa: E402


def a_share_decision(exit_on: date = EXIT) -> dict:
    closes = series()
    p = size_to_risk("EFA", "rsi2_reversion", Side.BUY, closes[-1], closes,
                     risk_budget=1500.0, equity=100_000.0, exit_on=exit_on)
    return {"executed": True, "strategy": p.strategy, "structure": _structure_dict(p)}, p


def broker_row(symbol: str, qty: int, market_value: float) -> dict:
    return {"symbol": symbol, "qty": str(qty), "market_value": str(market_value)}


def test_a_share_position_survives_the_round_trip():
    """A share leg missing from the record is a position the exit path cannot see — and for
    a one-session strategy an invisible position is the strategy silently gone."""
    decision, p = a_share_decision()
    rows = [broker_row("EFA", p.share.qty, p.share.notional)]
    held = held_positions(rows, [decision])
    assert len(held) == 1
    assert held[0].is_share and held[0].share_side == "long"
    assert held[0].underlying == "EFA"
    assert held[0].expiry == EXIT


def test_the_share_exit_fires_on_the_day_not_before():
    decision, p = a_share_decision()
    held = held_positions([broker_row("EFA", p.share.qty, p.share.notional)], [decision])[0]
    assert evaluate_exit(held, EXIT - timedelta(days=1)) is None  # still inside its session
    out = evaluate_exit(held, EXIT)
    assert out is not None and out.reason.value == "time_stop"


def test_the_share_exit_fires_on_a_WINNER_too():
    """No target: the measured strategy takes whatever one session gives. Letting a winner
    run is a different strategy from the one that produced the numbers."""
    decision, p = a_share_decision()
    up = p.share.notional * 1.05
    held = held_positions([broker_row("EFA", p.share.qty, up)], [decision])[0]
    assert held.unrealized > 0
    assert evaluate_exit(held, EXIT) is not None


def test_share_unrealized_has_the_right_sign_both_ways():
    decision, p = a_share_decision()
    n = p.share.notional
    long_up = held_positions([broker_row("EFA", p.share.qty, n * 1.02)], [decision])[0]
    long_dn = held_positions([broker_row("EFA", p.share.qty, n * 0.98)], [decision])[0]
    assert long_up.unrealized > 0 and long_dn.unrealized < 0


def test_option_rules_never_run_on_a_share_position():
    """assignment risk and short_strikes are meaningless here; the clock is the only rule."""
    decision, p = a_share_decision()
    held = held_positions([broker_row("EFA", p.share.qty, p.share.notional)], [decision])[0]
    assert held.short_strikes == ()
    # deep in its holding period, with a spot that would trip assignment logic on an option
    assert evaluate_exit(held, EXIT - timedelta(days=1), spot=1.0) is None


def test_the_kill_switch_still_flattens_a_share_position():
    decision, p = a_share_decision()
    held = held_positions([broker_row("EFA", p.share.qty, p.share.notional)], [decision])[0]
    out = evaluate_exit(held, EXIT - timedelta(days=1), kill_switch=True)
    assert out is not None and out.reason.value == "kill_switch"
