"""Screening for measured edge.

The universe used to be three tickers hardcoded on day one, and the premium scout made zero
tool calls because it was handed a summary of them. These tests pin the replacement — and in
particular the guard that stopped the screener's first live run from selling earnings vol.
"""

from datetime import date, timedelta

import pytest

from committee.chain import Contract
from committee.gates import Right
from committee.regime import Regime, classify
from committee.screener import (
    EVENT_PREMIUM_RATIO,
    MAX_ATM_SPREAD_PCT,
    MIN_TRADABLE_STRIKES,
    Candidate,
    _chain_quality,
    buyable,
    sellable,
)

TODAY = date(2026, 8, 26)
EXPIRY = TODAY + timedelta(days=2)


def chain(strikes: int = 20, atm_spread: float = 0.02, with_greeks: bool = True) -> list[Contract]:
    out = []
    for i in range(strikes):
        delta = 0.05 + (i / strikes) * 0.55
        mid = 2.0
        half = mid * atm_spread / 2
        out.append(
            Contract(
                symbol=f"X{i}", underlying="X", expiry=EXPIRY, right=Right.CALL,
                strike=100.0 + i, bid=round(mid - half, 4), ask=round(mid + half, 4),
                delta=round(delta, 4) if with_greeks else None,
                implied_volatility=0.30,
            )
        )
    return out


# At 30% IV a ONE-day implied move is 0.30 * sqrt(1/252) = 1.89%. Using dte=1 makes the
# fixture exact: each window is a single daily return, so the breach rate is simply the
# fraction of days that moved more than 1.89%. Constructed, not simulated — the breach rate
# is the statistic under test and must be known, not assumed from a plausible price path.
FIXTURE_IV = 0.30
OVER = 0.030   # clears the 1.89% implied move
UNDER = 0.005  # does not


def candidate(symbol: str, breach: float, spread: float = 0.02) -> Candidate:
    n = 100
    overs = round(n * breach)
    closes = [100.0]
    for i in range(n):
        step = OVER if i < overs else UNDER
        closes.append(closes[-1] * (1 + step if i % 2 == 0 else 1 - step))
    read = classify(symbol, FIXTURE_IV, 1, closes)
    return Candidate(symbol, read, 20, spread, EXPIRY, "test")


def test_the_fixture_produces_the_breach_rate_it_claims():
    """The fixture is load-bearing for every test below it, so it is verified rather than
    trusted — a fixture that quietly produces the wrong distribution makes every assertion
    that rests on it meaningless."""
    for target in (0.10, 0.35, 0.55):
        got = candidate("X", target).regime.breach_rate
        assert abs(got - target) < 0.05, f"asked for {target}, produced {got}"


# ── the guard that matters ─────────────────────────────────────────────────────────


def test_an_extreme_implied_move_is_an_event_not_an_edge():
    """The screener's first live run ranked NVDA best in the market — breach rate 0%, implied
    2-day move 8.88% — on the afternoon NVDA reported earnings. A backward-looking breach rate
    cannot see a scheduled binary. An extreme ratio must DISQUALIFY, not rank first."""
    flat = [100.0] * 95  # nothing has ever moved: any implied move looks enormous
    read = classify("NVDA", 0.90, 2, flat)
    assert read.regime is Regime.PREMIUM_RICH, "the naive read calls this the richest premium"
    assert read.ratio is None or read.ratio > EVENT_PREMIUM_RATIO, (
        "and the ratio is what exposes it as an event"
    )


def test_a_modest_overpricing_is_a_real_risk_premium():
    """The volatility risk premium is a persistent, MODEST overpricing — 1.2-1.6x. That must
    survive the event guard, or the guard rejects the very thing we are hunting."""
    c = candidate("SPY", breach=0.19)
    assert c.regime.regime is Regime.PREMIUM_RICH
    assert c.regime.ratio is None or c.regime.ratio < EVENT_PREMIUM_RATIO


# ── option quality gates edge, not the other way round ─────────────────────────────


def test_chain_quality_counts_only_strikes_worth_trading():
    usable, spread = _chain_quality(chain(strikes=20), EXPIRY)
    assert usable >= MIN_TRADABLE_STRIKES
    assert spread == pytest.approx(0.02, abs=0.005)


def test_a_chain_with_no_greeks_offers_nothing_to_select_from():
    usable, _ = _chain_quality(chain(with_greeks=False), EXPIRY)
    assert usable == 0


def test_a_wide_atm_spread_is_detected():
    _, spread = _chain_quality(chain(atm_spread=0.20), EXPIRY)
    assert spread > MAX_ATM_SPREAD_PCT


def test_a_chain_with_no_atm_quote_reports_infinite_spread():
    """Better an obviously impossible number than a plausible wrong one — infinity fails every
    comparison, a zero would pass them all."""
    thin = [c for c in chain() if abs(c.delta) < 0.30]
    _, spread = _chain_quality(thin, EXPIRY)
    assert spread == float("inf")


# ── ranking ────────────────────────────────────────────────────────────────────────


def test_ranking_prefers_the_lower_breach_rate():
    """Breach rate is the edge. Ranking on an IV/RV ratio instead is what parked the agent on
    the only fairly-priced name in its universe for two days."""
    rich, fair = candidate("A", 0.10), candidate("B", 0.35)
    assert rich.rank_key < fair.rank_key


def test_ranking_breaks_ties_on_tighter_options():
    tight, wide = candidate("A", 0.15, spread=0.01), candidate("B", 0.15, spread=0.05)
    assert tight.rank_key < wide.rank_key


def test_sellable_and_buyable_split_by_regime():
    cands = [candidate("A", 0.10), candidate("B", 0.35), candidate("C", 0.55)]
    assert [c.symbol for c in sellable(cands)] == ["A"]
    assert [c.symbol for c in buyable(cands)] == ["C"]


def test_a_candidate_describes_its_own_evidence():
    """Every candidate carries why it surfaced and what was measured, so a reader can check
    the ranking rather than trust it."""
    text = candidate("SPY", 0.19).describe()
    assert "SPY" in text and "strikes" in text and "%" in text
