"""Re-validate ORB on data the strategy has never seen.

    .venv/bin/python scripts/backtest_orb.py QQQ SPY IWM TSLA

The archived research fit these parameters on Aug 2025 - Feb 2026. Everything after Feb 2026
is genuinely out of sample: it did not exist when the parameters were chosen, so it cannot
have been fit to. That is a far stronger test than the archived walk-forward, and it is the
direct answer to the fact that the headline "Sharpe 3.31" was the best of a 288-combination
sweep that was never itself validated.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from committee.market import AlpacaRest, load_dev_vars  # noqa: E402
from committee.orb import Bar, ORBConfig, backtest, evaluate  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
# The archived study ended here. Everything after is untouched by the parameter choice.
FIT_PERIOD_END = date(2026, 2, 6)


def fetch_bars(rest: AlpacaRest, symbol: str, start: date, end: date) -> list[Bar]:
    out: list[Bar] = []
    page = None
    while True:
        url = (
            f"{rest._data}/v2/stocks/{symbol}/bars?timeframe=5Min"
            f"&start={start.isoformat()}&end={end.isoformat()}&limit=10000&feed=iex"
        )
        if page:
            url += f"&page_token={page}"
        payload = rest._get(url)
        for b in payload.get("bars", []) or []:
            out.append(
                Bar(
                    t=datetime.fromisoformat(b["t"].replace("Z", "+00:00")),
                    o=float(b["o"]), h=float(b["h"]), l=float(b["l"]),
                    c=float(b["c"]), v=float(b["v"]),
                )
            )
        page = payload.get("next_page_token")
        if not page:
            return out


def main() -> int:
    symbols = [s.upper() for s in (sys.argv[1:] or ["QQQ"])]
    rest = AlpacaRest(load_dev_vars(ROOT / ".dev.vars"))
    today = datetime.now(timezone.utc).date()

    print(f"Out-of-sample window: {FIT_PERIOD_END} -> {today}")
    print("(the archived parameters were fit on Aug 2025 - Feb 2026, so none of this was seen)\n")

    for sym in symbols:
        try:
            bars = fetch_bars(rest, sym, FIT_PERIOD_END, today - timedelta(days=1))
        except Exception as exc:  # noqa: BLE001
            print(f"{sym}: fetch failed — {type(exc).__name__}: {exc}")
            continue
        if len(bars) < 500:
            print(f"{sym}: only {len(bars)} bars, not enough to judge")
            continue

        sessions = len({b.session for b in bars})
        trades = backtest(bars, ORBConfig())
        perf = evaluate(trades)
        print(f"{sym}: {len(bars):,} bars over {sessions} sessions")
        print(f"   {perf.summary()}")
        if perf.trades:
            per_week = perf.trades / max(sessions / 5, 1)
            print(f"   {per_week:.1f} trades/week")
            by_reason: dict[str, int] = {}
            for t in trades:
                by_reason[t.reason or "?"] = by_reason.get(t.reason or "?", 0) + 1
            print(f"   exits: {by_reason}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
