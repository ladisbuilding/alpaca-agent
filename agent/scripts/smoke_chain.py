"""Smoke test against the LIVE Alpaca chain — proves the strategy layer works on real data.

    python3 scripts/smoke_chain.py QQQ

Reads credentials from ../.dev.vars. Read-only: fetches snapshots and builds candidate
structures, places nothing. Run this before every session — a chain that has changed shape
(new expiries, thin quotes, missing greeks) shows up here rather than in a live decision.
"""

from __future__ import annotations

import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from committee.chain import (  # noqa: E402
    LiquidityFilter,
    contracts_from_snapshots,
    expiries_within,
    select_by_delta,
    usable,
)
from committee.gates import (  # noqa: E402
    PortfolioState,
    Right,
    RiskConfig,
    evaluate,
    summarize,
    verify_defined_risk,
)
from committee.strategy import (  # noqa: E402
    DirectionalConfig,
    IncomeConfig,
    build_credit_vertical,
    build_debit_vertical,
    build_iron_condor,
)

ET = timezone(timedelta(hours=-4))


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    path = Path(__file__).resolve().parents[2] / ".dev.vars"
    if not path.exists():
        sys.exit(f"missing {path} — see README")
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def get(url: str, env: dict[str, str]) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "APCA-API-KEY-ID": env["ALPACA_API_KEY_ID"],
            "APCA-API-SECRET-KEY": env["ALPACA_API_SECRET_KEY"],
            "User-Agent": "alpaca-committee/0.1",
        },
    )
    import json

    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main() -> int:
    underlying = (sys.argv[1] if len(sys.argv) > 1 else "QQQ").upper()
    env = load_env()

    account = get(f"{env['ALPACA_PAPER_ENDPOINT']}/account", env)
    equity = float(account["equity"])
    print(f"account {account['account_number']}  equity ${equity:,.2f}  "
          f"options L{account.get('options_trading_level')}")

    payload = get(
        f"{env['ALPACA_DATA_ENDPOINT']}/v1beta1/options/snapshots/{underlying}"
        f"?feed=indicative&limit=1000",
        env,
    )
    contracts = contracts_from_snapshots(payload)
    liq = LiquidityFilter()
    tradable = usable(contracts, liq)
    with_greeks = [c for c in contracts if c.delta is not None]

    print(f"\n{underlying}: {len(contracts)} contracts parsed, "
          f"{len(with_greeks)} with greeks, {len(tradable)} pass liquidity")
    if not tradable:
        print("!! nothing tradable — widen the fetch or check the feed")
        return 1

    today = date.today()
    income = IncomeConfig()
    expiries = expiries_within(tradable, today, income.min_dte, income.max_dte)
    print(f"expiries in {income.min_dte}-{income.max_dte} DTE window: "
          f"{[e.isoformat() for e in expiries] or 'none'}")
    if not expiries:
        print("!! no expiry in window (weekend/holiday?) — widen max_dte to inspect")
        return 1

    expiry = expiries[0]
    sp = select_by_delta(tradable, Right.PUT, expiry, -income.short_delta)
    sc = select_by_delta(tradable, Right.CALL, expiry, income.short_delta)
    print(f"\n{expiry} — {income.short_delta:.0%} delta targets:")
    if sp:
        print(f"  put  {sp.strike:>8.2f}  d {sp.delta:+.3f}  {sp.bid:.2f}/{sp.ask:.2f}  IV {sp.implied_volatility}")
    if sc:
        print(f"  call {sc.strike:>8.2f}  d {sc.delta:+.3f}  {sc.bid:.2f}/{sc.ask:.2f}  IV {sc.implied_volatility}")

    portfolio = PortfolioState(
        equity=equity,
        cash=float(account["cash"]),
        buying_power=float(account["buying_power"]),
        realized_pnl_today=0.0,
    )
    config = RiskConfig()
    now = datetime.now(ET)
    # Ask Alpaca rather than assuming — half-days and holidays make a local guess wrong.
    clock = get(f"{env['ALPACA_PAPER_ENDPOINT']}/clock", env)
    market_open = bool(clock.get("is_open"))
    print(f"\nmarket {'OPEN' if market_open else 'CLOSED'} "
          f"(next open {clock.get('next_open')})")

    candidates = [
        ("iron_condor", build_iron_condor(tradable, expiry, income)),
        ("put_credit", build_credit_vertical(tradable, expiry, Right.PUT, income)),
        ("call_credit", build_credit_vertical(tradable, expiry, Right.CALL, income)),
        ("call_debit", build_debit_vertical(tradable, expiry, Right.CALL, DirectionalConfig())),
        ("put_debit", build_debit_vertical(tradable, expiry, Right.PUT, DirectionalConfig())),
    ]

    print("\ncandidates:")
    built = 0
    for name, p in candidates:
        if p is None:
            print(f"  {name:<14} — no sound structure available")
            continue
        built += 1
        derived = verify_defined_risk(p)
        if derived is None:
            agree = "n/a"  # debit verticals have no protective leg to measure against
        elif abs(derived - p.max_loss) < 0.01:
            agree = "ok"
        else:
            agree = "MISMATCH"
        result = evaluate(p, portfolio, config, now, market_open=market_open)
        print(
            f"  {name:<14} credit ${p.net_credit:>8.2f}  maxloss ${p.max_loss:>8.2f}  "
            f"spread {p.bid_ask_pct:>6.1%}  geometry {agree}  -> {summarize(result)}"
        )
        for reason in result.reasons:
            print(f"       - {reason}")

    print(f"\n{built}/{len(candidates)} structures built from the live chain")
    return 0 if built else 1


if __name__ == "__main__":
    raise SystemExit(main())
