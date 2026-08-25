"""Strategy layer tests against a synthetic but realistically-shaped chain.

The chain fixture mimics Alpaca's actual snapshot payload, including the detail that deep
in-the-money contracts arrive with no greeks block — the thing that makes a small sample
look like a paywall.
"""

from datetime import date

import pytest

from committee.chain import (
    Contract,
    FillAssumption,
    LiquidityFilter,
    contracts_from_snapshots,
    expiries_within,
    parse_occ_symbol,
    select_by_delta,
    select_wing,
    usable,
)
from committee.gates import (
    PortfolioState,
    Right,
    RiskConfig,
    Side,
    evaluate,
    has_uncovered_short,
    verify_defined_risk,
)
from committee.strategy import (
    DirectionalConfig,
    IncomeConfig,
    build_credit_vertical,
    build_debit_vertical,
    build_iron_condor,
)

TODAY = date(2026, 8, 25)
EXPIRY = date(2026, 8, 28)
SPOT = 709.0


def occ(strike: float, right: str) -> str:
    return f"QQQ260828{right}{int(strike * 1000):08d}"


def synthetic_chain() -> list[Contract]:
    """Strikes 680..740 in $1 steps, as a real QQQ chain is near the money. Delta is
    approximated from distance to spot so a ~16-delta strike lands predictably; prices
    decay away from the money."""
    out: list[Contract] = []
    for strike in range(680, 741):
        for right in (Right.PUT, Right.CALL):
            moneyness = (strike - SPOT) / SPOT
            if right is Right.CALL:
                delta = max(0.01, min(0.99, 0.5 - moneyness * 22))
            else:
                delta = -max(0.01, min(0.99, 0.5 + moneyness * 22))
            distance = abs(strike - SPOT)
            mid = max(0.05, 8.0 - distance * 0.22)
            out.append(
                Contract(
                    symbol=occ(strike, "C" if right is Right.CALL else "P"),
                    underlying="QQQ",
                    expiry=EXPIRY,
                    right=right,
                    strike=float(strike),
                    bid=round(mid - 0.03, 2),
                    ask=round(mid + 0.03, 2),
                    delta=round(delta, 4),
                    implied_volatility=0.20,
                )
            )
    return out


# ── OCC parsing ────────────────────────────────────────────────────────────────────


def test_parse_occ_symbol():
    parsed = parse_occ_symbol("QQQ260826P00696000")
    assert parsed == ("QQQ", date(2026, 8, 26), Right.PUT, 696.0)


def test_parse_occ_symbol_handles_calls_and_fractional_strikes():
    assert parse_occ_symbol("SPY260828C00512500") == ("SPY", date(2026, 8, 28), Right.CALL, 512.5)


@pytest.mark.parametrize("bad", ["QQQ", "AAPL", "QQQ26088P00696000", "QQQ269928P00696000", ""])
def test_parse_occ_symbol_rejects_non_options(bad):
    """A stray equity ticker in a payload must be skipped, not crash the run."""
    assert parse_occ_symbol(bad) is None


def test_contracts_from_snapshots_keeps_contracts_without_greeks():
    """Deep-ITM contracts arrive with no greeks block. They must survive parsing with
    delta=None so the caller can see how much of the chain is unusable — silently
    dropping them is what makes a chain look emptier than it is."""
    payload = {
        "snapshots": {
            "QQQ260828P00696000": {
                "latestQuote": {"bp": 0.98, "ap": 1.05},
                "greeks": {"delta": -0.164},
                "impliedVolatility": 0.222,
            },
            "QQQ260828C00495000": {"latestQuote": {"bp": 208.0, "ap": 215.0}},  # deep ITM, no greeks
            "NOT_AN_OPTION": {"latestQuote": {"bp": 1.0, "ap": 2.0}},
        }
    }
    parsed = contracts_from_snapshots(payload)
    assert len(parsed) == 2  # the non-option is skipped
    by_symbol = {c.symbol: c for c in parsed}
    assert by_symbol["QQQ260828P00696000"].delta == pytest.approx(-0.164)
    assert by_symbol["QQQ260828C00495000"].delta is None


# ── selection ──────────────────────────────────────────────────────────────────────


def test_select_by_delta_finds_the_nearest_short_put():
    chain = synthetic_chain()
    pick = select_by_delta(chain, Right.PUT, EXPIRY, -0.16)
    assert pick is not None
    assert pick.right is Right.PUT
    assert abs(pick.delta + 0.16) < 0.06, f"got delta {pick.delta}"
    assert pick.strike < SPOT, "a 16-delta put must be out of the money"


def test_select_by_delta_finds_the_nearest_short_call():
    pick = select_by_delta(synthetic_chain(), Right.CALL, EXPIRY, 0.16)
    assert pick is not None
    assert pick.strike > SPOT, "a 16-delta call must be out of the money"


def test_select_by_delta_returns_none_without_greeks():
    stripped = [
        Contract(c.symbol, c.underlying, c.expiry, c.right, c.strike, c.bid, c.ask, delta=None)
        for c in synthetic_chain()
    ]
    assert select_by_delta(stripped, Right.PUT, EXPIRY, -0.16) is None


def test_select_wing_sits_further_out_of_the_money():
    chain = synthetic_chain()
    short = select_by_delta(chain, Right.PUT, EXPIRY, -0.16)
    wing = select_wing(chain, Right.PUT, EXPIRY, short.strike, 5.0)
    assert wing is not None
    assert wing.strike < short.strike
    assert short.strike - wing.strike == pytest.approx(5.0)


def test_select_wing_for_calls_goes_the_other_way():
    chain = synthetic_chain()
    short = select_by_delta(chain, Right.CALL, EXPIRY, 0.16)
    wing = select_wing(chain, Right.CALL, EXPIRY, short.strike, 5.0)
    assert wing.strike > short.strike


def test_liquidity_filter_rejects_unquotable_and_crossed_contracts():
    f = LiquidityFilter()
    good = Contract("s", "QQQ", EXPIRY, Right.PUT, 690.0, 1.00, 1.06, delta=-0.16)
    no_bid = Contract("s", "QQQ", EXPIRY, Right.PUT, 690.0, 0.00, 1.06, delta=-0.16)
    crossed = Contract("s", "QQQ", EXPIRY, Right.PUT, 690.0, 1.20, 1.00, delta=-0.16)
    wide = Contract("s", "QQQ", EXPIRY, Right.PUT, 690.0, 0.50, 2.00, delta=-0.16)
    no_greeks = Contract("s", "QQQ", EXPIRY, Right.PUT, 690.0, 1.00, 1.06, delta=None)
    assert f.accepts(good)
    assert not f.accepts(no_bid)
    assert not f.accepts(crossed)
    assert not f.accepts(wide)
    assert not f.accepts(no_greeks)


def test_expiries_within_respects_the_dte_window():
    chain = synthetic_chain()  # all at EXPIRY, 3 DTE from TODAY
    assert expiries_within(chain, TODAY, 1, 9) == [EXPIRY]  # 3 DTE
    assert expiries_within(chain, TODAY, 5, 9) == []


# ── iron condor ────────────────────────────────────────────────────────────────────


def test_build_iron_condor_produces_a_valid_defined_risk_structure():
    p = build_iron_condor(synthetic_chain(), EXPIRY, IncomeConfig())
    assert p is not None
    assert p.strategy == "iron_condor"
    assert len(p.legs) == 4
    assert not has_uncovered_short(p), "every short must be covered"
    assert p.max_loss > 0 and p.net_credit > 0


def test_condor_max_loss_agrees_with_the_independent_gate_derivation():
    """The builder and the gate compute max loss by different routes. If they disagree,
    MISREPORTED_RISK fires — so this equality is what lets a correct condor through."""
    p = build_iron_condor(synthetic_chain(), EXPIRY, IncomeConfig())
    derived = verify_defined_risk(p)
    assert derived is not None
    assert p.max_loss == pytest.approx(derived, abs=0.01)


def test_condor_shorts_straddle_the_spot():
    p = build_iron_condor(synthetic_chain(), EXPIRY, IncomeConfig())
    shorts = [l for l in p.legs if l.side is Side.SELL]
    short_put = next(l for l in shorts if l.right is Right.PUT)
    short_call = next(l for l in shorts if l.right is Right.CALL)
    assert short_put.strike < SPOT < short_call.strike


def test_conservative_fill_pays_less_than_mid():
    """The default fill assumption must be the pessimistic one — a strategy that only
    clears its thresholds at mid will not clear them live."""
    chain = synthetic_chain()
    cons = build_iron_condor(chain, EXPIRY, IncomeConfig(fill=FillAssumption.CONSERVATIVE))
    mid = build_iron_condor(chain, EXPIRY, IncomeConfig(fill=FillAssumption.MID))
    assert cons.net_credit < mid.net_credit
    assert IncomeConfig().fill is FillAssumption.CONSERVATIVE


def test_condor_scales_with_quantity():
    one = build_iron_condor(synthetic_chain(), EXPIRY, IncomeConfig(qty=1))
    three = build_iron_condor(synthetic_chain(), EXPIRY, IncomeConfig(qty=3))
    assert three.net_credit == pytest.approx(one.net_credit * 3)
    assert all(l.qty == 3 for l in three.legs)


def test_condor_returns_none_on_an_empty_chain():
    assert build_iron_condor([], EXPIRY, IncomeConfig()) is None


def test_condor_returns_none_when_no_wings_exist():
    """Only the two short strikes are listed — there is nothing to buy for protection,
    so the builder must decline rather than emit a naked structure."""
    chain = [c for c in synthetic_chain() if c.strike in (698.0, 720.0)]
    assert build_iron_condor(chain, EXPIRY, IncomeConfig()) is None


def test_condor_survives_the_gates():
    p = build_iron_condor(synthetic_chain(), EXPIRY, IncomeConfig())
    portfolio = PortfolioState(
        equity=100_000.0, cash=100_000.0, buying_power=400_000.0, realized_pnl_today=0.0
    )
    from datetime import datetime, timedelta, timezone

    now = datetime(2026, 8, 25, 11, 0, tzinfo=timezone(timedelta(hours=-4)))
    result = evaluate(p, portfolio, RiskConfig(), now)
    assert result.approved, f"blocked by {result.blocked_by}: {result.reasons}"


# ── credit verticals ───────────────────────────────────────────────────────────────


def test_put_credit_spread_is_bullish_shaped():
    p = build_credit_vertical(synthetic_chain(), EXPIRY, Right.PUT, IncomeConfig())
    assert p is not None and p.strategy == "put_credit_spread"
    short = next(l for l in p.legs if l.side is Side.SELL)
    long = next(l for l in p.legs if l.side is Side.BUY)
    assert long.strike < short.strike < SPOT


def test_call_credit_spread_is_bearish_shaped():
    p = build_credit_vertical(synthetic_chain(), EXPIRY, Right.CALL, IncomeConfig())
    assert p is not None and p.strategy == "call_credit_spread"
    short = next(l for l in p.legs if l.side is Side.SELL)
    long = next(l for l in p.legs if l.side is Side.BUY)
    assert SPOT < short.strike < long.strike


def test_credit_vertical_max_loss_matches_the_gate():
    p = build_credit_vertical(synthetic_chain(), EXPIRY, Right.PUT, IncomeConfig())
    assert p.max_loss == pytest.approx(verify_defined_risk(p), abs=0.01)


# ── directional sleeve ─────────────────────────────────────────────────────────────


def test_call_debit_spread_is_defined_risk_and_pays_a_debit():
    p = build_debit_vertical(synthetic_chain(), EXPIRY, Right.CALL, DirectionalConfig())
    assert p is not None and p.strategy == "call_debit_spread"
    assert p.net_credit < 0, "a debit spread costs money"
    assert p.max_loss == pytest.approx(-p.net_credit), "max loss on a debit spread is the debit"
    assert p.max_profit > 0
    assert not has_uncovered_short(p)


def test_put_debit_spread_is_bearish_shaped():
    p = build_debit_vertical(synthetic_chain(), EXPIRY, Right.PUT, DirectionalConfig())
    assert p is not None and p.strategy == "put_debit_spread"
    long = next(l for l in p.legs if l.side is Side.BUY)
    short = next(l for l in p.legs if l.side is Side.SELL)
    assert short.strike < long.strike, "the short must be further OTM than the long"


def test_debit_spread_survives_the_gates():
    p = build_debit_vertical(synthetic_chain(), EXPIRY, Right.CALL, DirectionalConfig())
    portfolio = PortfolioState(
        equity=100_000.0, cash=100_000.0, buying_power=400_000.0, realized_pnl_today=0.0
    )
    from datetime import datetime, timedelta, timezone

    now = datetime(2026, 8, 25, 11, 0, tzinfo=timezone(timedelta(hours=-4)))
    result = evaluate(p, portfolio, RiskConfig(), now)
    assert result.approved, f"blocked by {result.blocked_by}: {result.reasons}"


# ── nomination parsing ─────────────────────────────────────────────────────────────
# Both cases below are real scout output that produced bad nominations in a live run.

from committee.cycle import parse_nominations  # noqa: E402

UNIVERSE = ["QQQ", "SPY", "IWM"]


def test_a_prose_caveat_is_not_a_ticker():
    """A live scout ended with 'Note: both expiries are 0-1 DTE...' and the parser
    nominated a ticker called NOTE, which then went through the gates as a real
    candidate."""
    text = (
        "QQQ: income — median IV 23-26% vs ~12.4% realized. Conviction 3.\n"
        "SPY: income — IV/RV ~3x, deepest chain. Conviction 4.\n"
        "Note: both expiries are 0-1 DTE, so gamma/pin risk is elevated.\n"
    )
    noms = parse_nominations(text, "scout_premium", "income", UNIVERSE)
    assert [n.underlying for n in noms] == ["QQQ", "SPY"]
    assert "NOTE" not in [n.underlying for n in noms]


def test_a_scout_restating_its_pick_counts_once():
    """The directional scout argued in prose and then restated the pick as a summary
    line. Both parsed, so one nomination became two and the same structure was built
    and gated twice."""
    text = (
        "QQQ: -5.0% over six sessions, persistent lower-highs, bearish continuation bias.\n"
        "\n"
        "QQQ: directional, bearish, six straight down days, conviction 3.\n"
    )
    noms = parse_nominations(text, "scout_directional", "directional", UNIVERSE)
    assert len(noms) == 1
    assert noms[0].underlying == "QQQ"
    assert noms[0].direction == "bearish"


def test_symbols_outside_the_universe_are_rejected():
    """Scouts are told to nominate from the universe only, so anything else is a parse
    artifact rather than a pick."""
    text = "NVDA: income — rich IV. Conviction 5.\nQQQ: income — also rich. Conviction 3.\n"
    noms = parse_nominations(text, "scout_premium", "income", UNIVERSE)
    assert [n.underlying for n in noms] == ["QQQ"]


def test_an_empty_reply_yields_no_nominations():
    """Returning nothing is explicitly a valid scout outcome, not an error."""
    assert parse_nominations("Nothing qualifies today.", "scout_premium", "income", UNIVERSE) == []


def test_conviction_and_direction_are_read_from_the_line():
    noms = parse_nominations(
        "SPY: income — bearish setup, conviction 5.", "scout_premium", "income", UNIVERSE
    )
    assert noms[0].conviction == 5
    assert noms[0].direction == "bearish"


def test_conviction_survives_trailing_punctuation():
    """'conviction 5.' has a trailing period, so a bare isdigit() check misses it and
    silently defaults to 3 — flattening the ordering that decides what gets debated."""
    for line, expected in [
        ("QQQ: income — rich IV. Conviction 5.", 5),
        ("QQQ: income — rich IV, conviction 4", 4),
        ("QQQ: income — rich IV (conviction: 2)", 2),
        ("QQQ: income — rich IV, conviction 4/5", 4),
        ("QQQ: income — no number given", 3),
    ]:
        got = parse_nominations(line, "scout_premium", "income", UNIVERSE)[0].conviction
        assert got == expected, f"{line!r} -> {got}, expected {expected}"
