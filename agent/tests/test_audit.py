"""Auditor tests.

The headline test reconstructs the actual historical failure — 15 real decisions recorded as
72 trades, reporting $2,015 on a book that had made $89 — and asserts this auditor catches it.
A safeguard built in response to a specific incident should be tested against that incident.
"""

from datetime import datetime, timezone

import pytest

from committee.audit import (
    AuditReport,
    Fill,
    audit,
    fills_from_activities,
    format_report,
)

NOW = datetime(2026, 8, 28, 15, 0, tzinfo=timezone.utc)


def account(equity: float = 100_089.0, last_equity: float = 100_000.0) -> dict:
    return {"equity": str(equity), "last_equity": str(last_equity)}


def fill_activity(symbol: str, side: str = "sell", qty: float = 1, price: float = 1.0, id_: str = "x") -> dict:
    return {
        "id": id_,
        "activity_type": "FILL",
        "symbol": symbol,
        "side": side,
        "qty": str(qty),
        "price": str(price),
        "transaction_time": "2026-08-28T14:30:00Z",
    }


def condor_decision(
    fingerprint: str = "QQQ|iron_condor|2026-08-28|...",
    realized: float | None = None,
    max_profit: float = 120.0,
    symbols: tuple[str, ...] = ("A", "B", "C", "D"),
    executed: bool = True,
) -> dict:
    return {
        "executed": executed,
        "strategy": "iron_condor",
        "structure": {
            "underlying": "QQQ",
            "fingerprint": fingerprint,
            "max_profit": max_profit,
            "legs": [{"symbol": s} for s in symbols],
        },
        **({"realized_pnl": realized} if realized is not None else {}),
    }


# ── parsing ────────────────────────────────────────────────────────────────────────


def test_only_fills_are_counted_not_orders():
    """An order records intent; a fill records what happened. Counting unfilled orders is
    the same class of error as counting legs."""
    activities = [
        fill_activity("QQQ260828P00696000", id_="1"),
        {"id": "2", "activity_type": "ORDER", "symbol": "QQQ260828C00716000"},
        {"id": "3", "activity_type": "DIV", "symbol": "QQQ"},
    ]
    assert len(fills_from_activities(activities)) == 1


def test_malformed_rows_are_skipped_not_fatal():
    activities = [fill_activity("A", id_="1"), {"activity_type": "FILL", "symbol": "B"}]
    assert len(fills_from_activities(activities)) == 1


def test_fill_cash_flow_is_signed_by_side():
    sell = Fill("1", "A", "sell", 1, 1.20, NOW)
    buy = Fill("2", "A", "buy", 1, 1.20, NOW)
    assert sell.cash_flow == pytest.approx(120.0)
    assert buy.cash_flow == pytest.approx(-120.0)


# ── the incident this module exists for ────────────────────────────────────────────


def test_it_catches_the_2015_dollar_failure():
    """15 real decisions recorded as 72 trades, at a 100% win rate.

    The same structure re-entered repeatedly is the mechanism. This asserts BOTH tells fire:
    the duplicate fingerprint and the implausible win rate.
    """
    duplicated = [
        condor_decision(fingerprint="QQQ|iron_condor|2026-08-28|SAME", realized=28.0)
        for _ in range(6)
    ]
    report = audit(account(equity=100_168.0), [], duplicated, now=NOW)

    dupes = [a for a in report.anomalies if "was executed" in a]
    assert dupes, "a structure entered 6 times must be flagged"
    assert "dedup gate has a hole" in dupes[0]

    win_rate = [a for a in report.anomalies if "win rate" in a]
    assert win_rate, "a 100% win rate over 6 settled trades must be flagged"


def test_order_rows_are_reported_next_to_decisions():
    """One four-leg condor is ONE decision and FOUR rows. Conflating them is how 15
    becomes 72."""
    report = audit(account(), [], [condor_decision(realized=89.0)], now=NOW)
    assert report.distinct_decisions == 1
    assert report.order_rows == 4
    assert "1 decisions across 4 order rows" in report.headline()


# ── reconciliation against the broker ──────────────────────────────────────────────


def test_attributed_pnl_must_reconcile_with_the_brokers_equity_change():
    """Our attribution is the claim; the broker's equity change is the check."""
    report = audit(
        account(equity=100_089.0, last_equity=100_000.0),
        [],
        [condor_decision(realized=89.0)],
        now=NOW,
    )
    assert report.reconciles
    assert report.unattributed == pytest.approx(0.0)
    assert not [a for a in report.anomalies if "reconcile" in a]


def test_an_unexplained_gap_is_reported_not_absorbed():
    """The broker says +$500; we can only explain +$89. The $411 gap is the finding."""
    report = audit(
        account(equity=100_500.0, last_equity=100_000.0),
        [],
        [condor_decision(realized=89.0)],
        now=NOW,
    )
    assert not report.reconciles
    assert report.unattributed == pytest.approx(411.0)
    assert any("does not reconcile" in a for a in report.anomalies)
    assert "DOES NOT RECONCILE" in report.headline()


# ── other ways the headline could lie ──────────────────────────────────────────────


def test_fills_with_no_decision_record_are_flagged():
    """Something traded that the committee did not decide."""
    report = audit(
        account(),
        [fill_activity("UNKNOWN260828P00500000", id_="1")],
        [condor_decision(realized=89.0, symbols=("A", "B", "C", "D"))],
        now=NOW,
    )
    assert any("no matching decision record" in a for a in report.anomalies)


def test_decisions_with_no_fills_are_flagged():
    """A recorded trade that never happened inflates the decision count."""
    report = audit(account(), [], [condor_decision(realized=89.0)], now=NOW)
    assert any("no fills at the broker" in a for a in report.anomalies)


def test_a_return_above_max_profit_is_impossible_not_impressive():
    report = audit(
        account(equity=100_500.0, last_equity=100_000.0),
        [fill_activity("A", id_="1")],
        [condor_decision(realized=500.0, max_profit=120.0)],
        now=NOW,
    )
    assert any("cannot return more than its maximum" in a for a in report.anomalies)


def test_a_plausible_win_rate_is_not_flagged():
    """Pairs with the implausible-rate test: the check must key on the rate, not fire on
    every book that is winning."""
    decisions = [
        condor_decision(fingerprint=f"fp{i}", realized=(30.0 if i < 4 else -60.0)) for i in range(6)
    ]
    report = audit(account(equity=100_000.0, last_equity=100_000.0), [], decisions, now=NOW)
    assert not [a for a in report.anomalies if "win rate" in a]


def test_a_high_win_rate_on_a_tiny_sample_is_not_flagged():
    """Two wins out of two is not evidence of anything."""
    decisions = [condor_decision(fingerprint=f"fp{i}", realized=30.0) for i in range(2)]
    report = audit(account(), [], decisions, now=NOW)
    assert not [a for a in report.anomalies if "win rate" in a]


# ── empty and open books ───────────────────────────────────────────────────────────


def test_an_empty_book_audits_clean():
    report = audit(account(equity=100_000.0, last_equity=100_000.0), [], [], now=NOW)
    assert report.distinct_decisions == 0
    assert report.reconciles
    assert any("nothing to overstate" in n for n in report.notes)


def test_unrealized_marks_are_excluded_from_the_attributed_figure():
    """Open positions are not results. Counting marks as P&L is how paper books flatter."""
    report = audit(
        account(equity=100_300.0, last_equity=100_000.0),
        [fill_activity("A", id_="1")],
        [condor_decision(realized=None, symbols=("A",))],
        now=NOW,
    )
    assert report.attributed == pytest.approx(0.0)
    assert any("not results" in n for n in report.notes)
    # the open mark shows up as unattributed rather than being quietly booked as profit
    assert report.unattributed == pytest.approx(300.0)


def test_unexecuted_decisions_are_not_audited():
    report = audit(account(), [], [condor_decision(executed=False, realized=999.0)], now=NOW)
    assert report.distinct_decisions == 0
    assert report.attributed == pytest.approx(0.0)


def test_format_report_states_the_reconciliation_verdict():
    report = audit(
        account(equity=100_500.0, last_equity=100_000.0),
        [],
        [condor_decision(realized=89.0)],
        now=NOW,
    )
    text = format_report(report)
    assert "DOES NOT RECONCILE" in text
    assert "ANOMALIES" in text
    assert "iron_condor" in text


# ── the bug the Auditor found ──────────────────────────────────────────────────────

from committee.market import _positions_to_state  # noqa: E402


def test_sizing_uses_options_buying_power_not_margin_buying_power():
    """`buying_power` is the 4x-margin number ($400k on a $100k account). Defined-risk
    options are cash-secured, so `options_buying_power` is what actually binds. Sizing off
    the margin figure authorises 4x the intended risk.

    Found by the Auditor agent against a live empty account, before any trade was placed.
    """
    account = {
        "equity": "100000",
        "cash": "100000",
        "buying_power": "400000",
        "regt_buying_power": "200000",
        "options_buying_power": "100000",
        "last_equity": "100000",
    }
    state = _positions_to_state(account, [])
    assert state.buying_power == pytest.approx(100_000.0), "must not use the 4x margin figure"
    assert state.buying_power != pytest.approx(400_000.0)


def test_sizing_falls_back_to_cash_when_options_buying_power_is_absent():
    """A missing field must not silently fall back to the 4x number."""
    account = {"equity": "50000", "cash": "50000", "buying_power": "200000", "last_equity": "50000"}
    state = _positions_to_state(account, [])
    assert state.buying_power == pytest.approx(50_000.0)


def test_an_open_mark_explains_the_gap_and_is_a_note_not_an_anomaly():
    """Equity moves with an open position while attributed P&L deliberately does not, so the
    gap is legitimate. Flagging it every time would make the anomaly list noise."""
    report = audit(
        account(equity=99_996.0, last_equity=100_000.0),
        [fill_activity("A", id_="1")],
        [condor_decision(realized=None, symbols=("A",))],
        now=NOW,
        open_unrealized=-4.0,
    )
    assert not [a for a in report.anomalies if "reconcile" in a]
    assert any("Marks are not results" in n for n in report.notes)


def test_a_gap_larger_than_the_open_marks_is_still_an_anomaly():
    """Only the part explained by marks is excused; a residual beyond that is a real finding."""
    report = audit(
        account(equity=100_500.0, last_equity=100_000.0),
        [fill_activity("A", id_="1")],
        [condor_decision(realized=None, symbols=("A",))],
        now=NOW,
        open_unrealized=-4.0,
    )
    anomaly = [a for a in report.anomalies if "reconcile" in a]
    assert anomaly
    assert "open marks" in anomaly[0]
