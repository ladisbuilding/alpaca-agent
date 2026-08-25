"""Does the ORB breakout predict anything AFTER the session it fires in?

ORB as designed is intraday: enter mid-morning, out by 15:55. Wrapping a same-day trade in
options means crossing the bid-ask twice within hours, and the Bear measured that friction at
13-27% of credit — more than the whole intraday edge.

So the question that decides whether ORB can be an options strategy at all is narrow:
**does the signal still predict direction 1, 2, 3 and 5 sessions later?**

If yes, a 5-15 DTE debit spread held a few days is a legitimate expression and the friction
amortises over a real move. If no, ORB is an equity strategy and we should stop trying to
make it something else.

Measured against a same-day baseline so "it predicts" means "better than the drift", not
"the market went up".
"""

from __future__ import annotations

import statistics
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from committee.market import AlpacaRest, load_dev_vars  # noqa: E402
from committee.orb import ET, Bar, Direction, ORBConfig, backtest  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIT_PERIOD_END = date(2026, 2, 6)
HORIZONS = (1, 2, 3, 5)


def fetch(rest: AlpacaRest, symbol: str, start: date, end: date, tf: str) -> list[dict]:
    out, page = [], None
    while True:
        url = (
            f"{rest._data}/v2/stocks/{symbol}/bars?timeframe={tf}"
            f"&start={start.isoformat()}&end={end.isoformat()}&limit=10000&feed=iex"
        )
        if page:
            url += f"&page_token={page}"
        p = rest._get(url)
        out += p.get("bars", []) or []
        page = p.get("next_page_token")
        if not page:
            return out


def main() -> int:
    symbols = [s.upper() for s in (sys.argv[1:] or ["QQQ", "SPY", "TSLA"])]
    rest = AlpacaRest(load_dev_vars(ROOT / ".dev.vars"))
    today = datetime.now(timezone.utc).date()

    print("Does an ORB breakout predict direction AFTER its own session?")
    print(f"Out-of-sample window {FIT_PERIOD_END} -> {today}. Returns are signed BY the")
    print("breakout direction, so positive = the signal was right.\n")

    for sym in symbols:
        intraday = [
            Bar(
                t=datetime.fromisoformat(b["t"].replace("Z", "+00:00")),
                o=float(b["o"]), h=float(b["h"]), l=float(b["l"]),
                c=float(b["c"]), v=float(b["v"]),
            )
            for b in fetch(rest, sym, FIT_PERIOD_END, today - timedelta(days=1), "5Min")
        ]
        daily_raw = fetch(rest, sym, FIT_PERIOD_END - timedelta(days=10), today, "1Day")
        daily = {
            datetime.fromisoformat(b["t"].replace("Z", "+00:00")).astimezone(ET).date(): float(b["c"])
            for b in daily_raw
        }
        days = sorted(daily)
        idx = {d: i for i, d in enumerate(days)}

        trades = backtest(intraday, ORBConfig())
        if not trades:
            print(f"{sym}: no signals\n")
            continue

        print(f"{sym}: {len(trades)} breakout signals over {len(days)} sessions")
        # Baseline: the same horizons measured on every session, unsigned — what you'd get
        # from simply being long. If the signal has no edge it will match this.
        for h in HORIZONS:
            signed, base = [], []
            for t in trades:
                i = idx.get(t.session)
                if i is None or i + h >= len(days):
                    continue
                entry_close = daily[days[i]]
                later = daily[days[i + h]]
                if entry_close <= 0:
                    continue
                move = (later - entry_close) / entry_close
                signed.append(move if t.direction is Direction.LONG else -move)
            for i in range(len(days) - h):
                c0, c1 = daily[days[i]], daily[days[i + h]]
                if c0 > 0:
                    base.append((c1 - c0) / c0)
            if len(signed) < 20:
                print(f"   +{h}d: only {len(signed)} samples")
                continue
            mean = statistics.mean(signed)
            sd = statistics.pstdev(signed) or 1e-9
            hit = sum(1 for x in signed if x > 0) / len(signed)
            t_stat = mean / (sd / (len(signed) ** 0.5))
            print(
                f"   +{h}d: n={len(signed):>3}  mean {mean:+.3%}  hit {hit:.1%}  "
                f"t={t_stat:+.2f}  (long-only baseline {statistics.mean(base):+.3%})"
            )
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
