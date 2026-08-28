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


# ── joining broker legs back to the decisions that opened them ─────────────────────

from committee.manage import held_positions  # noqa: E402


def broker_leg(symbol: str, market_value: float) -> dict:
    return {"symbol": symbol, "market_value": str(market_value)}


def executed_condor() -> dict:
    return {
        "executed": True,
        "strategy": "iron_condor",
        "structure": {
            "underlying": "QQQ",
            "fingerprint": "fp1",
            "expiry": "2026-09-04",
            "net_credit": 100.0,
            "max_profit": 100.0,
            "max_loss": 400.0,
            "legs": [
                {"symbol": "A", "side": "sell", "strike": 690.0},
                {"symbol": "B", "side": "buy", "strike": 685.0},
                {"symbol": "C", "side": "sell", "strike": 720.0},
                {"symbol": "D", "side": "buy", "strike": 725.0},
            ],
        },
    }


def test_four_broker_legs_become_one_managed_position():
    """The broker has no memory that four legs were one condor. Counting legs is the same
    error family that turned 15 decisions into 72 trades."""
    legs = [broker_leg(s, -12.5) for s in ("A", "B", "C", "D")]
    held = held_positions(legs, [executed_condor()])
    assert len(held) == 1
    assert held[0].strategy == "iron_condor"
    assert held[0].short_strikes == (690.0, 720.0)


def test_current_value_is_the_cost_to_close():
    """Net market value is negative on a credit structure; the cost to close is its size."""
    legs = [broker_leg(s, v) for s, v in (("A", -40.0), ("B", 5.0), ("C", -30.0), ("D", 5.0))]
    held = held_positions(legs, [executed_condor()])
    assert held[0].current_value == pytest.approx(60.0)
    assert held[0].unrealized == pytest.approx(40.0)  # took $100, costs $60 to close


def test_a_closed_position_is_not_managed():
    """No broker legs remain, so it expired or was already closed — nothing to do."""
    assert held_positions([], [executed_condor()]) == []


def test_a_partially_closed_structure_is_still_managed():
    """Two of four legs remain — still a live position and still needs an exit decision."""
    held = held_positions([broker_leg("A", -40.0), broker_leg("B", 5.0)], [executed_condor()])
    assert len(held) == 1


def test_legs_the_decision_log_cannot_explain_are_skipped_not_guessed():
    """An orphan leg is the Auditor's job to report, not this function's to invent a
    position from."""
    held = held_positions([broker_leg("UNKNOWN", -10.0)], [executed_condor()])
    assert held == []


def test_a_malformed_expiry_is_skipped_rather_than_crashing_the_cycle():
    bad = executed_condor()
    bad["structure"]["expiry"] = "not-a-date"
    assert held_positions([broker_leg("A", -10.0)], [bad]) == []


def test_a_structure_ordered_twice_produces_ONE_managed_position():
    """We ordered the same IWM condor several times over a week. Each executed decision record
    produced its own HeldPosition, so one real structure generated THREE exit decisions: the
    first close consumed the legs and the next two hunted for positions that no longer existed.

    Same duplicate-counting failure the audit layer exists to catch — here in the code that
    manages risk."""
    legs = [broker_leg(s, -12.5) for s in ("A", "B", "C", "D")]
    reordered = [executed_condor(), executed_condor(), executed_condor()]
    held = held_positions(legs, reordered)
    assert len(held) == 1, f"one structure, one position — got {len(held)}"


def test_two_genuinely_different_structures_are_both_managed():
    """Pairs with the test above: dedup must key on identity, not collapse everything."""
    other = executed_condor()
    other["structure"]["fingerprint"] = "fp2"
    other["structure"]["legs"] = [{"symbol": s, "side": "sell", "strike": 1.0} for s in ("E", "F")]
    legs = [broker_leg(s, -10.0) for s in ("A", "B", "C", "D", "E", "F")]
    held = held_positions(legs, [executed_condor(), other])
    assert len(held) == 2


def test_legs_are_claimed_by_only_one_position():
    """Two decision records whose legs OVERLAP must not both claim them — otherwise the book
    reads larger than it is, and the second exit closes something already gone."""
    overlapping = executed_condor()
    overlapping["structure"]["fingerprint"] = "fp-different"
    held = held_positions([broker_leg(s, -10.0) for s in ("A", "B")], [executed_condor(), overlapping])
    assert len(held) == 1


def test_a_partially_closed_structure_is_labelled_partial():
    """A structure missing legs is no longer what was risk-assessed, and the exit reason should
    say so rather than pretending it is intact."""
    held = held_positions([broker_leg("A", -40.0), broker_leg("B", 5.0)], [executed_condor()])
    assert len(held) == 1
    assert "partial" in held[0].strategy


# ── a close is only closed when the BROKER says so ────────────────────────────────

from committee.cycle import verify_closed  # noqa: E402

# The verbatim rejection Alpaca returned on 2026-08-28, closing a WINNING IWM condor.
ALPACA_REJECTION = (
    "The closing order was rejected by Alpaca:\n\n"
    "**Error (HTTP 403, code 40310000):** \"order has been rejected due to no "
    "available quote for symbol. please reenter with a limit\""
)


def test_the_old_heuristic_could_not_see_this_rejection():
    """Why the bug existed: success was 'output does not begin with ERROR or DENIED'.

    This rejection begins with neither, so a refused order read as a completed exit.
    """
    assert not ALPACA_REJECTION.startswith(("ERROR", "DENIED"))


def test_a_rejected_close_is_not_closed_while_the_legs_remain():
    """The order was submitted and refused, so the broker still holds all four legs."""
    legs = [broker_leg(s, -12.5) for s in ("A", "B", "C", "D")]
    assert not verify_closed(
        "fp1", submitted=True, refetch_positions=lambda: legs,
        open_decisions=[executed_condor()],
    )


def test_a_close_is_recorded_only_once_the_legs_are_gone():
    assert verify_closed(
        "fp1", submitted=True, refetch_positions=lambda: [],
        open_decisions=[executed_condor()],
    )


def test_a_partial_close_is_not_a_close():
    """Two legs filled, two rejected — the position is still live and still needs an exit."""
    legs = [broker_leg(s, -12.5) for s in ("A", "B")]
    assert not verify_closed(
        "fp1", submitted=True, refetch_positions=lambda: legs,
        open_decisions=[executed_condor()],
    )


def test_an_unverifiable_close_is_not_closed():
    """If the book cannot be re-read, the honest answer is 'not closed', never 'closed'."""
    def boom() -> list[dict]:
        raise RuntimeError("broker unreachable")

    assert not verify_closed(
        "fp1", submitted=True, refetch_positions=boom, open_decisions=[executed_condor()],
    )
    assert not verify_closed(
        "fp1", submitted=True, refetch_positions=None, open_decisions=[executed_condor()],
    )


def test_no_order_submitted_is_never_a_close():
    """An empty book must not read as success when nothing was ever sent."""
    assert not verify_closed(
        "fp1", submitted=False, refetch_positions=lambda: [],
        open_decisions=[executed_condor()],
    )
