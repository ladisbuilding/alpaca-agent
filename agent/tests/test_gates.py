"""Every gate must be proven to BITE.

For each gate there are two tests: one where the gate blocks, and one where the same
proposal passes once the offending condition is removed. A test that only asserts
"approved is False" can pass for the wrong reason — a typo elsewhere blocking every
proposal would look identical. The paired baseline is what makes each assertion mean
something.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from committee.gates import (
    CONTRACT_SIZE,
    Leg,
    OpenPosition,
    PortfolioState,
    Proposal,
    Right,
    RiskConfig,
    Side,
    evaluate,
    has_uncovered_short,
    summarize,
    verify_defined_risk,
)

ET = timezone(timedelta(hours=-4))
NOW = datetime(2026, 8, 25, 11, 0, tzinfo=ET)  # Tuesday, mid-session
EXPIRY = date(2026, 8, 28)


def condor(qty: int = 1, credit: float | None = None, underlying: str = "QQQ") -> Proposal:
    """A 696/691 put spread + 716/721 call spread — $5 wings, so max loss is
    $500/contract less the credit received."""
    if credit is None:
        credit = 120.0 * qty  # credit scales with size, exactly as max loss does
    legs = (
        Leg(f"{underlying}260828P00696000", Side.SELL, qty, Right.PUT, 696.0, EXPIRY),
        Leg(f"{underlying}260828P00691000", Side.BUY, qty, Right.PUT, 691.0, EXPIRY),
        Leg(f"{underlying}260828C00716000", Side.SELL, qty, Right.CALL, 716.0, EXPIRY),
        Leg(f"{underlying}260828C00721000", Side.BUY, qty, Right.CALL, 721.0, EXPIRY),
    )
    # $5 wings on both sides, non-overlapping shorts => can only lose on ONE side
    max_loss = 5.0 * CONTRACT_SIZE * qty - credit
    return Proposal(
        underlying=underlying,
        strategy="iron_condor",
        legs=legs,
        max_loss=max_loss,
        max_profit=credit,
        net_credit=credit,
        bid_ask_pct=0.04,
    )


def healthy_portfolio(**overrides) -> PortfolioState:
    base = dict(
        equity=100_000.0,
        cash=100_000.0,
        buying_power=400_000.0,
        realized_pnl_today=0.0,
        open_positions=(),
    )
    base.update(overrides)
    return PortfolioState(**base)


CONFIG = RiskConfig()


def test_baseline_condor_is_approved():
    """The control. If this ever fails, every 'blocked' test below is meaningless."""
    result = evaluate(condor(), healthy_portfolio(), CONFIG, NOW)
    assert result.approved, f"baseline should pass, blocked by {result.blocked_by}: {result.reasons}"
    assert summarize(result).startswith("APPROVED")


# ── UNDEFINED RISK ─────────────────────────────────────────────────────────────────


def test_naked_short_is_blocked():
    naked = Proposal(
        underlying="QQQ",
        strategy="naked_put",
        legs=(Leg("QQQ260828P00696000", Side.SELL, 1, Right.PUT, 696.0, EXPIRY),),
        max_loss=69_600.0,
        max_profit=120.0,
        net_credit=120.0,
    )
    result = evaluate(naked, healthy_portfolio(), CONFIG, NOW)
    assert not result.approved
    assert "UNDEFINED_RISK" in result.blocked_by


def test_has_uncovered_short_detects_ratio_spread():
    ratioed = Proposal(
        underlying="QQQ",
        strategy="ratio_spread",
        legs=(
            Leg("QQQ260828P00696000", Side.SELL, 2, Right.PUT, 696.0, EXPIRY),
            Leg("QQQ260828P00691000", Side.BUY, 1, Right.PUT, 691.0, EXPIRY),
        ),
        max_loss=500.0,
        max_profit=100.0,
        net_credit=100.0,
    )
    assert has_uncovered_short(ratioed) is True
    assert has_uncovered_short(condor()) is False


def test_misreported_risk_is_caught():
    """A strategy claiming less risk than its geometry implies must not get through —
    otherwise every percentage-based cap below is sizing off a fiction."""
    liar = condor()
    understated = Proposal(
        underlying=liar.underlying,
        strategy=liar.strategy,
        legs=liar.legs,
        max_loss=50.0,  # actually $380
        max_profit=liar.max_profit,
        net_credit=liar.net_credit,
        bid_ask_pct=liar.bid_ask_pct,
    )
    result = evaluate(understated, healthy_portfolio(), CONFIG, NOW)
    assert not result.approved
    assert "MISREPORTED_RISK" in result.blocked_by


def test_verify_defined_risk_matches_geometry():
    derived = verify_defined_risk(condor(qty=1, credit=120.0))
    # ONE $5 wing at the 100 multiplier, less the credit — not both wings summed
    assert derived == pytest.approx(5.0 * 100 - 120.0)


def test_verify_defined_risk_sums_both_sides_when_shorts_overlap():
    """An inverted structure CAN finish in the money on both sides, so the conservative
    sum is correct there. Pairs with the test above to prove the max/sum branch works."""
    inverted = Proposal(
        underlying="QQQ",
        strategy="guts",
        legs=(
            Leg("a", Side.SELL, 1, Right.PUT, 716.0, EXPIRY),   # short put ABOVE
            Leg("b", Side.BUY, 1, Right.PUT, 711.0, EXPIRY),
            Leg("c", Side.SELL, 1, Right.CALL, 696.0, EXPIRY),  # short call BELOW
            Leg("d", Side.BUY, 1, Right.CALL, 701.0, EXPIRY),
        ),
        max_loss=10_000.0,
        max_profit=1.0,
        net_credit=100.0,
    )
    assert verify_defined_risk(inverted) == pytest.approx(5.0 * 100 * 2 - 100.0)


def test_verify_defined_risk_returns_none_for_unverifiable_shape():
    naked = Proposal(
        underlying="QQQ",
        strategy="naked_put",
        legs=(Leg("QQQ260828P00696000", Side.SELL, 1, Right.PUT, 696.0, EXPIRY),),
        max_loss=1.0,
        max_profit=1.0,
        net_credit=1.0,
    )
    assert verify_defined_risk(naked) is None


# ── SIZE AND PORTFOLIO CAPS ────────────────────────────────────────────────────────


def test_trade_larger_than_per_trade_cap_is_blocked():
    """Sized from the config so raising the cap cannot silently disarm the test that guards
    it — a trade just over the allowance, whatever the allowance currently is."""
    cap = CONFIG.max_loss_per_trade_pct * 100_000
    qty = int(cap // (5.0 * CONTRACT_SIZE - 120.0)) + 1
    result = evaluate(condor(qty=qty), healthy_portfolio(), CONFIG, NOW)
    assert not result.approved
    assert "TRADE_TOO_LARGE" in result.blocked_by


def test_a_trade_just_inside_the_per_trade_cap_is_allowed():
    cap = CONFIG.max_loss_per_trade_pct * 100_000
    qty = max(int(cap // (5.0 * CONTRACT_SIZE - 120.0)), 1)
    result = evaluate(condor(qty=qty), healthy_portfolio(), CONFIG, NOW)
    assert "TRADE_TOO_LARGE" not in result.blocked_by


def test_same_trade_passes_when_equity_supports_it():
    """Proves TRADE_TOO_LARGE keys on the ratio, not on the raw size."""
    big = condor(qty=3)
    result = evaluate(big, healthy_portfolio(equity=1_000_000.0), CONFIG, NOW)
    assert "TRADE_TOO_LARGE" not in result.blocked_by


def test_daily_loss_limit_halts_trading():
    down = healthy_portfolio(realized_pnl_today=-3_000.0)  # exactly -3% of 100k
    result = evaluate(condor(), down, CONFIG, NOW)
    assert not result.approved
    assert "DAILY_LOSS_LIMIT" in result.blocked_by


def test_just_inside_daily_loss_limit_still_trades_but_warns():
    down = healthy_portfolio(realized_pnl_today=-2_999.0)
    result = evaluate(condor(), down, CONFIG, NOW)
    assert result.approved
    assert any("today" in w for w in result.warnings)


def test_portfolio_risk_cap_blocks_when_book_is_full():
    existing = tuple(
        OpenPosition(f"SYM{i}", "iron_condor", f"fp{i}", 1_300.0, EXPIRY) for i in range(7)
    )
    loaded = healthy_portfolio(open_positions=existing)  # $9,100 of $10,000 cap deployed
    # per-trade cap raised so this test isolates the PORTFOLIO cap, not the per-trade one
    result = evaluate(condor(qty=3), loaded, RiskConfig(max_loss_per_trade_pct=0.05), NOW)
    assert not result.approved
    assert "PORTFOLIO_RISK_CAP" in result.blocked_by


def test_portfolio_risk_cap_allows_the_same_trade_on_an_emptier_book():
    """Pairs with the test above: proves the cap keys on deployed risk, not on the trade."""
    existing = (OpenPosition("SYM0", "iron_condor", "fp0", 1_300.0, EXPIRY),)
    result = evaluate(
        condor(qty=3),
        healthy_portfolio(open_positions=existing),
        RiskConfig(max_loss_per_trade_pct=0.05),
        NOW,
    )
    assert "PORTFOLIO_RISK_CAP" not in result.blocked_by


def test_too_many_positions_is_blocked():
    """Derived from the config, not hardcoded — otherwise raising a cap silently breaks the
    test that guards it, which is the opposite of what a guard is for."""
    existing = tuple(
        OpenPosition(f"SYM{i}", "iron_condor", f"fp{i}", 10.0, EXPIRY)
        for i in range(CONFIG.max_concurrent_positions)
    )
    result = evaluate(condor(), healthy_portfolio(open_positions=existing), CONFIG, NOW)
    assert not result.approved
    assert "TOO_MANY_POSITIONS" in result.blocked_by


def test_one_below_the_position_cap_still_trades():
    existing = tuple(
        OpenPosition(f"SYM{i}", "iron_condor", f"fp{i}", 10.0, EXPIRY)
        for i in range(CONFIG.max_concurrent_positions - 1)
    )
    result = evaluate(condor(), healthy_portfolio(open_positions=existing), CONFIG, NOW)
    assert "TOO_MANY_POSITIONS" not in result.blocked_by


def test_concentration_blocks_once_the_per_underlying_cap_is_reached():
    existing = tuple(
        OpenPosition("QQQ", "iron_condor", f"fp{i}", 100.0, EXPIRY)
        for i in range(CONFIG.max_positions_per_underlying)
    )
    result = evaluate(condor(underlying="QQQ"), healthy_portfolio(open_positions=existing), CONFIG, NOW)
    assert not result.approved
    assert "CONCENTRATION" in result.blocked_by


def test_concentration_allows_a_different_underlying():
    existing = tuple(
        OpenPosition("QQQ", "iron_condor", f"fp{i}", 100.0, EXPIRY)
        for i in range(CONFIG.max_positions_per_underlying)
    )
    result = evaluate(condor(underlying="SPY"), healthy_portfolio(open_positions=existing), CONFIG, NOW)
    assert "CONCENTRATION" not in result.blocked_by


# ── DEDUP — the gate that protects the P&L number itself ───────────────────────────


def test_duplicate_structure_is_blocked_while_still_live():
    p = condor()
    result = evaluate(
        p, healthy_portfolio(), CONFIG, NOW, recent_fingerprints=[(p.fingerprint, EXPIRY)]
    )
    assert not result.approved
    assert "DUPLICATE" in result.blocked_by


def test_same_structure_allowed_once_the_old_one_has_expired():
    """The dedup window is the opportunity's lifecycle, not a fixed clock. Once the
    prior structure's expiry has passed it is genuinely a new opportunity."""
    p = condor()
    stale = date(2026, 8, 22)  # already expired relative to NOW
    result = evaluate(
        p, healthy_portfolio(), CONFIG, NOW, recent_fingerprints=[(p.fingerprint, stale)]
    )
    assert "DUPLICATE" not in result.blocked_by


def test_fingerprint_distinguishes_different_strikes():
    a = condor()
    b = Proposal(
        underlying="QQQ",
        strategy="iron_condor",
        legs=(
            Leg("QQQ260828P00690000", Side.SELL, 1, Right.PUT, 690.0, EXPIRY),
            Leg("QQQ260828P00685000", Side.BUY, 1, Right.PUT, 685.0, EXPIRY),
            Leg("QQQ260828C00720000", Side.SELL, 1, Right.CALL, 720.0, EXPIRY),
            Leg("QQQ260828C00725000", Side.BUY, 1, Right.CALL, 725.0, EXPIRY),
        ),
        max_loss=880.0,
        max_profit=120.0,
        net_credit=120.0,
    )
    assert a.fingerprint != b.fingerprint


def test_fingerprint_is_stable_across_leg_ordering():
    a = condor()
    reordered = Proposal(
        underlying=a.underlying,
        strategy=a.strategy,
        legs=tuple(reversed(a.legs)),
        max_loss=a.max_loss,
        max_profit=a.max_profit,
        net_credit=a.net_credit,
    )
    assert a.fingerprint == reordered.fingerprint


# ── EXECUTION QUALITY ──────────────────────────────────────────────────────────────


def test_wide_spread_is_blocked():
    p = condor()
    wide = Proposal(
        underlying=p.underlying,
        strategy=p.strategy,
        legs=p.legs,
        max_loss=p.max_loss,
        max_profit=p.max_profit,
        net_credit=p.net_credit,
        bid_ask_pct=0.30,
    )
    result = evaluate(wide, healthy_portfolio(), CONFIG, NOW)
    assert not result.approved
    assert "WIDE_SPREAD" in result.blocked_by


def test_thin_credit_is_blocked():
    thin = condor(credit=20.0)  # $20 credit against ~$980 risk = 2%
    result = evaluate(thin, healthy_portfolio(), CONFIG, NOW)
    assert not result.approved
    assert "THIN_CREDIT" in result.blocked_by


# ── TIME AND STATE ─────────────────────────────────────────────────────────────────


def test_near_close_is_blocked():
    late = datetime(2026, 8, 25, 15, 50, tzinfo=ET)
    result = evaluate(condor(), healthy_portfolio(), CONFIG, late)
    assert not result.approved
    assert "NEAR_CLOSE" in result.blocked_by


def test_comfortably_before_close_is_allowed():
    fine = datetime(2026, 8, 25, 15, 40, tzinfo=ET)
    result = evaluate(condor(), healthy_portfolio(), CONFIG, fine)
    assert "NEAR_CLOSE" not in result.blocked_by


def test_market_closed_is_blocked():
    result = evaluate(condor(), healthy_portfolio(), CONFIG, NOW, market_open=False)
    assert not result.approved
    assert "MARKET_CLOSED" in result.blocked_by


def test_kill_switch_blocks_everything():
    result = evaluate(condor(), healthy_portfolio(), CONFIG, NOW, kill_switch=True)
    assert not result.approved
    assert "KILL_SWITCH" in result.blocked_by


def test_insufficient_buying_power_is_blocked():
    poor = healthy_portfolio(buying_power=300.0)  # usable = $240 after the 20% buffer
    result = evaluate(condor(), poor, CONFIG, NOW)
    assert not result.approved
    assert "INSUFFICIENT_BUYING_POWER" in result.blocked_by


# ── REPORTING ──────────────────────────────────────────────────────────────────────


def test_all_blocking_reasons_are_collected_not_just_the_first():
    """The decision log should show every rule a proposal broke. Short-circuiting would
    hide the second and third reasons and make refusals look narrower than they are."""
    oversized = int((CONFIG.max_loss_per_trade_pct * 100_000) // (5.0 * CONTRACT_SIZE - 120.0)) + 2
    result = evaluate(
        condor(qty=oversized),
        healthy_portfolio(realized_pnl_today=-5_000.0, buying_power=100.0),
        CONFIG,
        NOW,
        kill_switch=True,
    )
    assert not result.approved
    assert len(result.blocked_by) >= 4
    assert len(result.reasons) == len(result.blocked_by)
    assert all(r.strip() for r in result.reasons), "every block needs a human-readable reason"


def test_summarize_names_the_gates():
    result = evaluate(condor(), healthy_portfolio(), CONFIG, NOW, kill_switch=True)
    assert "KILL_SWITCH" in summarize(result)


def test_leg_rejects_nonpositive_qty():
    with pytest.raises(ValueError):
        Leg("QQQ260828P00696000", Side.SELL, 0, Right.PUT, 696.0, EXPIRY)


# ── timezone ───────────────────────────────────────────────────────────────────────

UTC = timezone.utc


def test_near_close_is_measured_in_eastern_not_wall_clock():
    """The container runs in UTC. A raw 15:48 reading looked like 12 minutes to the 16:00
    close when it was actually 11:48 ET — mid-session — which blocked every afternoon entry."""
    midday_et = datetime(2026, 8, 25, 15, 48, tzinfo=UTC)  # 11:48 ET
    result = evaluate(condor(), healthy_portfolio(), CONFIG, midday_et)
    assert "NEAR_CLOSE" not in result.blocked_by, result.reasons


def test_near_close_still_fires_when_it_actually_is_near_the_close():
    late_et = datetime(2026, 8, 25, 19, 50, tzinfo=UTC)  # 15:50 ET
    result = evaluate(condor(), healthy_portfolio(), CONFIG, late_et)
    assert "NEAR_CLOSE" in result.blocked_by


def test_near_close_agrees_across_timezones_for_the_same_instant():
    """The same moment expressed in UTC and in Pacific must reach the same verdict."""
    instant_utc = datetime(2026, 8, 25, 19, 50, tzinfo=UTC)
    instant_pt = instant_utc.astimezone(timezone(timedelta(hours=-7)))
    a = evaluate(condor(), healthy_portfolio(), CONFIG, instant_utc)
    b = evaluate(condor(), healthy_portfolio(), CONFIG, instant_pt)
    assert a.blocked_by == b.blocked_by
