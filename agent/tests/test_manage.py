"""Exit rules.

Every rule here exists because of something the committee found. The assignment rule in
particular came from a live Bear objection: "'Defined risk' ends at 4pm."
"""

from datetime import date

import pytest

from committee.manage import (
    ExitReason,
    HeldPosition,
    ManageConfig,
    evaluate_exit,
    review,
)

TODAY = date(2026, 8, 25)


def condor(
    expiry: date = date(2026, 9, 4),
    entry_credit: float = 100.0,
    current_value: float = 100.0,
    max_profit: float = 100.0,
    shorts: tuple[float, ...] = (690.0, 720.0),
) -> HeldPosition:
    return HeldPosition(
        fingerprint="fp",
        underlying="QQQ",
        strategy="iron_condor",
        expiry=expiry,
        entry_credit=entry_credit,
        max_profit=max_profit,
        max_loss=400.0,
        current_value=current_value,
        short_strikes=shorts,
    )


# ── nothing to do ──────────────────────────────────────────────────────────────────


def test_a_healthy_position_is_left_alone():
    """The control. Without this, every 'closes' test below could pass for the wrong reason."""
    assert evaluate_exit(condor(), TODAY) is None


# ── profit target ──────────────────────────────────────────────────────────────────


def test_closes_at_half_of_max_profit():
    """Took $100 credit, costs $50 to buy back → up $50 of $100 max."""
    d = evaluate_exit(condor(current_value=50.0), TODAY)
    assert d and d.reason is ExitReason.PROFIT_TARGET


def test_does_not_close_just_below_the_target():
    assert evaluate_exit(condor(current_value=51.0), TODAY) is None


def test_profit_target_works_on_debit_structures_too():
    """Paid $100, now worth $160 → up $60 against a $100 max profit."""
    p = HeldPosition("fp", "QQQ", "call_debit_spread", date(2026, 9, 4),
                     entry_credit=-100.0, max_profit=100.0, max_loss=100.0, current_value=160.0)
    d = evaluate_exit(p, TODAY)
    assert d and d.reason is ExitReason.PROFIT_TARGET


# ── stop loss ──────────────────────────────────────────────────────────────────────


def test_stops_out_at_twice_the_credit():
    """Took $100, now costs $300 to close → down $200 = 2x the credit."""
    d = evaluate_exit(condor(current_value=300.0), TODAY)
    assert d and d.reason is ExitReason.STOP_LOSS


def test_does_not_stop_just_inside_the_threshold():
    assert evaluate_exit(condor(current_value=299.0), TODAY) is None


# ── time and assignment — the rules that keep 'defined risk' true ──────────────────


def test_closes_at_the_time_stop_rather_than_carrying_into_expiry():
    d = evaluate_exit(condor(expiry=date(2026, 8, 26)), TODAY)
    assert d and d.reason is ExitReason.TIME_STOP


def test_assignment_risk_outranks_the_time_stop():
    """Both fire at 1 DTE; the assignment reason is the one worth recording, because it
    explains WHY carrying it is dangerous rather than just that a clock ran out."""
    d = evaluate_exit(condor(expiry=date(2026, 8, 26)), TODAY, spot=690.5)
    assert d and d.reason is ExitReason.ASSIGNMENT_RISK
    assert "overnight" in d.detail


def test_a_short_strike_far_from_spot_is_only_a_time_stop():
    d = evaluate_exit(condor(expiry=date(2026, 8, 26)), TODAY, spot=705.0)
    assert d and d.reason is ExitReason.TIME_STOP


def test_assignment_check_needs_a_spot_price():
    """Without spot we cannot measure moneyness — it must fall back to the time stop rather
    than silently skip the check."""
    d = evaluate_exit(condor(expiry=date(2026, 8, 26)), TODAY, spot=None)
    assert d and d.reason is ExitReason.TIME_STOP


# ── kill switch ────────────────────────────────────────────────────────────────────


def test_kill_switch_flattens_everything():
    d = evaluate_exit(condor(), TODAY, kill_switch=True)
    assert d and d.reason is ExitReason.KILL_SWITCH


# ── review across a book ───────────────────────────────────────────────────────────


def test_review_returns_only_positions_needing_action():
    book = [
        condor(),                                    # healthy
        condor(current_value=40.0),                  # at profit target
        condor(expiry=date(2026, 8, 26)),            # time stop
    ]
    decisions = review(book, TODAY)
    assert len(decisions) == 2
    assert {d.reason for d in decisions} == {ExitReason.PROFIT_TARGET, ExitReason.TIME_STOP}


def test_review_on_an_empty_book_is_quiet():
    assert review([], TODAY) == []


def test_unrealized_is_signed_correctly_for_both_structure_types():
    credit = condor(entry_credit=100.0, current_value=30.0)
    assert credit.unrealized == pytest.approx(70.0)
    debit = HeldPosition("f", "Q", "call_debit_spread", date(2026, 9, 4),
                         entry_credit=-100.0, max_profit=100.0, max_loss=100.0, current_value=130.0)
    assert debit.unrealized == pytest.approx(30.0)
