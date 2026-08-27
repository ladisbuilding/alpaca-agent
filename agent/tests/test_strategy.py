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


def test_a_scout_that_declines_is_taken_at_its_word():
    """A live scout wrote 'No nominations.' and then explained why — and the explanation,
    which mentioned QQQ, was parsed as a QQQ nomination. The ticker is in the universe and
    the line looked like any other, so the universe filter could not catch it."""
    text = (
        "No nominations.\n\n"
        "QQQ IV/RV 1.05x is cheap (not rich) — premium selling unpaid, favors debit "
        "strategies instead. SPY 1.19x and IWM 1.24x show no clear edge for sellers.\n"
    )
    assert parse_nominations(text, "scout_premium", "income", UNIVERSE) == []


def test_declining_phrases_are_matched_at_the_head_only():
    """A scout that nominates and later mentions standing down on ONE name must still have
    its nominations read."""
    text = (
        "QQQ: income — rich IV. Conviction 4.\n"
        "I am standing down on SPY specifically.\n"
    )
    noms = parse_nominations(text, "scout_premium", "income", UNIVERSE)
    assert [n.underlying for n in noms] == ["QQQ"]


# ── verdict parsing ────────────────────────────────────────────────────────────────

from committee.cycle import read_verdict  # noqa: E402


def test_a_negated_kill_is_not_a_kill():
    """Live text that inverted a real decision: the Bear recommended ALLOW at 1 lot and the
    committee's TAKE was recorded as BLOCKED, because 'kill' appeared inside 'not a kill'."""
    text = (
        "1. The case is mislabeled. NVDA reports inside the window.\n"
        "It's symmetric, not adverse, so not a kill — but the record should say so.\n\n"
        "**ALLOW, 1 lot ($303, 0.30%).**"
    )
    assert read_verdict(text) == "ALLOW"


def test_a_real_kill_is_read_as_kill():
    text = "Friction consumes the entire gain.\n\n**KILL** — not paid for the tail."
    assert read_verdict(text) == "KILL"


def test_the_last_verdict_wins():
    """The prompt asks for the verdict at the end, so a mention early in the reasoning must
    not outrank the conclusion."""
    text = "I considered whether to allow this.\n\nVERDICT: KILL — the tail is mispriced."
    assert read_verdict(text) == "KILL"


def test_verdict_ignores_longer_words():
    """ALLOWED / KILLED inside prose are not verdicts."""
    assert read_verdict("The structure would be killed by friction. ALLOW, 1 lot.") == "ALLOW"


def test_verdict_defaults_to_allow_when_absent():
    """Under the deploy-and-manage mandate, silence is not a refusal — a missing verdict
    should not silently block a trade the committee never rejected."""
    assert read_verdict("I have no strong view here.") == "ALLOW"


# ── sizing to the risk budget ──────────────────────────────────────────────────────

from committee.strategy import size_for_risk  # noqa: E402


def test_sizing_scales_a_structure_to_the_risk_budget():
    """Both winning condors made $21 and $12 — not because the edge was small, but because
    qty=1 with $5 wings caps max profit near $60 while using $400 of a $1,000 allowance."""
    chain = synthetic_chain()
    one = build_iron_condor(chain, EXPIRY, IncomeConfig(qty=1))
    sized = size_for_risk(
        lambda q: build_iron_condor(chain, EXPIRY, IncomeConfig(qty=q)), risk_budget=one.max_loss * 3
    )
    assert sized.legs[0].qty == 3
    assert sized.max_loss == pytest.approx(one.max_loss * 3, rel=0.01)
    assert sized.max_profit > one.max_profit


def test_sizing_never_goes_below_one_contract():
    """A budget too small for even one contract returns the single-contract structure — the
    gates then refuse it, which is where that decision belongs."""
    chain = synthetic_chain()
    sized = size_for_risk(lambda q: build_iron_condor(chain, EXPIRY, IncomeConfig(qty=q)), risk_budget=1.0)
    assert sized.legs[0].qty == 1


def test_sizing_respects_a_hard_quantity_ceiling():
    chain = synthetic_chain()
    sized = size_for_risk(
        lambda q: build_iron_condor(chain, EXPIRY, IncomeConfig(qty=q)),
        risk_budget=1_000_000.0,
        max_qty=4,
    )
    assert sized.legs[0].qty == 4


def test_sizing_passes_an_unbuildable_structure_through_as_none():
    assert size_for_risk(lambda q: None, risk_budget=1000.0) is None


def test_screened_candidates_are_valid_nomination_targets():
    """The ticker filter exists to reject parse artifacts — a caveat line once became a ticker
    called NOTE. Validating against the SEED universe alone turned it into a second, invisible
    universe cap, and it discarded a directional nomination for NVDA on a +9% post-earnings
    catalyst simply because NVDA was not one of three hardcoded seeds."""
    text = "NVDA | directional | bullish | post-earnings gap +7.7% with PT hikes | conviction 2"
    seeds_only = parse_nominations(text, "scout_directional", "directional", ["QQQ", "SPY", "IWM"])
    assert seeds_only == [], "the seed-only list is what discarded it"

    with_screened = parse_nominations(
        text, "scout_directional", "directional", ["QQQ", "SPY", "IWM", "NVDA"]
    )
    assert [n.underlying for n in with_screened] == ["NVDA"]
    assert with_screened[0].direction == "bullish"
    assert with_screened[0].conviction == 2


def test_the_artifact_guard_still_bites_with_a_wider_list():
    """Widening the allowed list must not reopen the hole it was closing."""
    text = "NVDA: bullish catalyst.\nNote: this is a caveat, not a pick.\n"
    noms = parse_nominations(text, "scout_directional", "directional", ["NVDA", "SPY"])
    assert [n.underlying for n in noms] == ["NVDA"]
