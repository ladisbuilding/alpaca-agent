"""Per-strategy switches.

The situation these exist for is one we are actually in: the income sleeve has been measured to
have no edge while the directional sleeve is still worth running. A global on/off cannot express
that — and worse, a global kill also stops MANAGEMENT, which leaves open positions abandoned.
"""

from datetime import date

import pytest

from committee.gates import (
    Leg,
    PortfolioState,
    Proposal,
    Right,
    RiskConfig,
    Side,
    evaluate,
)
from committee.manage import ExitReason, HeldPosition, review
from committee.switches import FAMILIES, Mode, Switches

EXPIRY = date(2026, 9, 4)


def test_defaults_are_all_active():
    s = Switches()
    assert s.all_active
    assert all(s.may_open(k) for k in ("iron_condor", "put_debit_spread", "calendar_call"))


def test_exit_only_blocks_entries_for_that_family_only():
    s = Switches.parse("income:exit_only")
    assert not s.may_open("iron_condor")
    assert not s.may_open("put_credit_spread")
    assert s.may_open("put_debit_spread"), "the directional sleeve must be unaffected"


def test_exit_only_does_not_flatten():
    """The whole point: stand down entries while still managing what is held. A position you
    have stopped managing is more dangerous than one you never opened."""
    s = Switches.parse("income:exit_only")
    assert not s.must_flatten("iron_condor")


def test_killed_flattens():
    s = Switches.parse("income:killed")
    assert not s.may_open("iron_condor")
    assert s.must_flatten("iron_condor")


def test_global_kill_overrides_everything():
    s = Switches.parse("income:active,directional:active", global_kill=True)
    assert not s.all_active
    for family in ("iron_condor", "put_debit_spread", "calendar_call"):
        assert not s.may_open(family)
        assert s.must_flatten(family)


@pytest.mark.parametrize("spec", ["", None, "garbage", "income:nonsense", "nosuchfamily:killed"])
def test_a_bad_spec_is_ignored_not_fatal(spec):
    """A typo in an env var must not stop a trading session. The effective modes are reported
    on every cycle, so a silently-ignored typo is visible rather than mysterious."""
    s = Switches.parse(spec)
    assert s.all_active


def test_every_known_strategy_maps_to_a_family():
    s = Switches()
    for strategy in (
        "iron_condor", "put_credit_spread", "call_credit_spread",
        "call_debit_spread", "put_debit_spread", "calendar_call", "calendar_put",
    ):
        assert s.family(strategy) in FAMILIES


def test_an_unknown_strategy_gets_a_family_rather_than_crashing():
    assert Switches().family("some_new_structure") in FAMILIES


# ── integration with the gates and the exit rules ──────────────────────────────────


def condor() -> Proposal:
    return Proposal(
        underlying="QQQ",
        strategy="iron_condor",
        legs=(
            Leg("a", Side.SELL, 1, Right.PUT, 696.0, EXPIRY),
            Leg("b", Side.BUY, 1, Right.PUT, 691.0, EXPIRY),
            Leg("c", Side.SELL, 1, Right.CALL, 716.0, EXPIRY),
            Leg("d", Side.BUY, 1, Right.CALL, 721.0, EXPIRY),
        ),
        max_loss=380.0, max_profit=120.0, net_credit=120.0, bid_ask_pct=0.04,
    )


def test_a_stood_down_family_is_blocked_by_the_gates():
    from datetime import datetime, timedelta, timezone

    now = datetime(2026, 8, 25, 15, 0, tzinfo=timezone(timedelta(hours=-4)))
    portfolio = PortfolioState(100_000.0, 100_000.0, 100_000.0, 0.0)
    s = Switches.parse("income:exit_only")

    blocked = evaluate(condor(), portfolio, RiskConfig(), now,
                       switch_reason=s.block_reason("iron_condor"))
    assert "STRATEGY_STOOD_DOWN" in blocked.blocked_by
    assert "EXIT-ONLY" in blocked.reasons[0]

    allowed = evaluate(condor(), portfolio, RiskConfig(), now, switch_reason=None)
    assert allowed.approved, "the control — without the switch it passes"


def held() -> HeldPosition:
    return HeldPosition("fp", "QQQ", "iron_condor", EXPIRY, 120.0, 120.0, 380.0, 110.0, (696.0,))


def test_a_killed_family_flattens_its_open_positions():
    decisions = review([held()], date(2026, 8, 25), switches=Switches.parse("income:killed"))
    assert len(decisions) == 1
    assert decisions[0].reason is ExitReason.STRATEGY_KILLED


def test_an_exit_only_family_keeps_managing_normally():
    """No forced flatten, and the ordinary rules still apply — the position is healthy so
    nothing fires."""
    decisions = review([held()], date(2026, 8, 25), switches=Switches.parse("income:exit_only"))
    assert decisions == []
