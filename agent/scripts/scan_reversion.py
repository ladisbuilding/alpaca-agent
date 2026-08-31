"""What would the RSI(2) sleeve do today? Read-only — no orders, no committee, no cost.

Prints the signal, the sizing, and every gate verdict, so the whole path can be inspected
before it is ever wired to an executor.

    .venv/bin/python scripts/scan_reversion.py
"""

from __future__ import annotations

import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from committee.gates import (  # noqa: E402
    OpenPosition,
    PortfolioState,
    RiskConfig,
    Side,
    evaluate,
    summarize,
)
from committee.market import AlpacaRest, load_dev_vars  # noqa: E402
from committee.reversion import BASKET, scan  # noqa: E402
from committee.shares import size_to_risk  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def closes(rest: AlpacaRest, sym: str, sessions: int = 400) -> list[float]:
    """Daily closes ending with the most recent session.

    ⚠️ feed=iex, not sip. This plan cannot query recent SIP data at all, so a sip request
    here returns 403 for TODAY and the scan would silently run on a series ending yesterday
    — which is a wrong signal rather than an error.
    """
    start = (date.today() - timedelta(days=sessions * 2)).isoformat()
    out, page = [], None
    while True:
        url = (
            f"{rest._data}/v2/stocks/{sym}/bars?timeframe=1Day&start={start}"
            f"&limit=10000&feed=iex&adjustment=split"
        )
        if page:
            url += f"&page_token={page}"
        payload = rest._get(url)
        out += payload.get("bars") or []
        page = payload.get("next_page_token")
        if not page:
            return [float(b["c"]) for b in out if b.get("c")]


def main() -> int:
    rest = AlpacaRest(load_dev_vars(ROOT / ".dev.vars"))
    account = rest.account()
    equity = float(account["equity"])
    config = RiskConfig()
    now = datetime.now(timezone.utc)

    series = {}
    for sym in BASKET:
        try:
            series[sym] = closes(rest, sym)
        except Exception as exc:  # noqa: BLE001
            print(f"  !! {sym}: {type(exc).__name__}: {exc}")
        time.sleep(0.12)

    print(f"Account {account['account_number']} — equity ${equity:,.2f}")
    print(f"Series: " + ", ".join(f"{k} {len(v)}" for k, v in series.items()) + "\n")

    signals = scan(series)
    if not signals:
        print("No RSI(2) signal in the basket today. A quiet day is a legitimate outcome.")
        return 0

    portfolio = PortfolioState(
        equity=equity,
        cash=float(account["cash"]),
        buying_power=float(account["buying_power"]),
        realized_pnl_today=equity - float(account["last_equity"]),
    )
    budget = equity * config.max_loss_per_trade_pct
    exit_on = date.today() + timedelta(days=1)

    # ⚠️ ACCUMULATE. These signals are NOT independent — the basket's mean pairwise daily
    # correlation is 0.51 (LQD/TLT/IEF sit at 0.89-0.92), so ~7 assets behave like 1.7
    # independent bets and they nearly all fire on the same day. Evaluating each against an
    # empty book, as this script first did, shows six APPROVEDs that could never all be
    # taken: the portfolio risk cap is the gate that says so, and it can only speak if
    # earlier positions are actually added to the book it sees.
    taken, running = [], portfolio
    for sig in signals:
        print(f"  {sig.describe()}")
        proposal = size_to_risk(
            sig.symbol, "rsi2_reversion",
            Side.BUY if sig.direction == "long" else Side.SELL,
            sig.ref_price, series[sig.symbol],
            risk_budget=budget, equity=equity, exit_on=exit_on,
        )
        if proposal is None:
            print("     -> could not size (insufficient history)\n")
            continue
        leg = proposal.share
        print(f"     size {leg.qty} shares, ${leg.notional:,.0f} notional, "
              f"stress {leg.stress_move:.2%} -> modelled max loss ${proposal.max_loss:,.0f}")
        verdict = evaluate(proposal, running, config, now)
        print(f"     {summarize(verdict)}\n")
        if verdict.approved:
            taken.append(proposal)
            running = PortfolioState(
                equity=running.equity, cash=running.cash,
                buying_power=running.buying_power,
                realized_pnl_today=running.realized_pnl_today,
                open_positions=running.open_positions + (
                    OpenPosition(proposal.underlying, proposal.strategy,
                                 proposal.fingerprint, proposal.max_loss, proposal.expiry,
                                 share_notional=leg.notional),
                ),
            )

    risk = sum(p.max_loss for p in taken)
    notional = sum(p.share.notional for p in taken)
    print(f"  TAKEN {len(taken)} of {len(signals)} signals — ${risk:,.0f} risk "
          f"({risk/equity:.1%} of equity), ${notional:,.0f} gross ({notional/equity:.0%})")
    print("  Risk is SUMMED, not root-summed: that is the perfectly-correlated worst case,")
    print("  which is the right assumption for a basket this correlated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
