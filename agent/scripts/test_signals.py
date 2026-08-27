"""Falsify technical signals cheaply, using the test that killed ORB.

The machinery matters more than any one signal: measure an edge on data that postdates the
idea, translate it through the instrument we would actually trade, and compare it against the
bid-ask we would actually pay. ORB passed the first two steps and died on the third — its edge
was $3.85 a contract and collecting it cost $4.00.

Every signal here is tested the same way, on the same out-of-sample window, and reported
whether it works or not. A negative result in ten minutes is the point.

    .venv/bin/python scripts/test_signals.py QQQ SPY IWM
"""

from __future__ import annotations

import statistics
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from committee.chain import contracts_from_snapshots  # noqa: E402
from committee.market import AlpacaRest, load_dev_vars  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
# The archived research ended here, so everything after is untouched by any idea in it.
OUT_OF_SAMPLE_FROM = date(2026, 2, 6)


def daily(rest: AlpacaRest, symbol: str, start: date, end: date) -> list[dict]:
    out, page = [], None
    while True:
        url = (
            f"{rest._data}/v2/stocks/{symbol}/bars?timeframe=1Day"
            f"&start={start.isoformat()}&end={end.isoformat()}&limit=10000&feed=iex"
        )
        if page:
            url += f"&page_token={page}"
        p = rest._get(url)
        out += p.get("bars", []) or []
        page = p.get("next_page_token")
        if not page:
            return out


# ── signals ────────────────────────────────────────────────────────────────────────
# Each returns a list of per-trade returns IN THE UNDERLYING, signed so positive means
# the signal was right.


def overnight(bars: list[dict]) -> list[float]:
    """Buy the close, sell the next open.

    The archive calls this "the Grandmother of All Market Anomalies" — nearly all index gains
    have historically accrued overnight, with intraday flat to negative.
    """
    return [
        (float(bars[i]["o"]) - float(bars[i - 1]["c"])) / float(bars[i - 1]["c"])
        for i in range(1, len(bars))
        if float(bars[i - 1]["c"])
    ]


def intraday(bars: list[dict]) -> list[float]:
    """The mirror: buy the open, sell the close. If the overnight effect is real, this is
    its negative — and testing both is how you tell a real anomaly from a data artifact."""
    return [
        (float(b["c"]) - float(b["o"])) / float(b["o"]) for b in bars if float(b["o"])
    ]


def gap_fade(bars: list[dict], threshold: float = 0.004) -> list[float]:
    """Fade an opening gap: short a gap up, buy a gap down, exit at the close."""
    out = []
    for i in range(1, len(bars)):
        prev_c, o, c = float(bars[i - 1]["c"]), float(bars[i]["o"]), float(bars[i]["c"])
        if not prev_c or not o:
            continue
        gap = (o - prev_c) / prev_c
        if abs(gap) < threshold:
            continue
        move = (c - o) / o
        out.append(-move if gap > 0 else move)  # fading, so a reversal is a win
    return out


def rsi(closes: list[float], period: int = 2) -> list[float | None]:
    out: list[float | None] = [None] * len(closes)
    for i in range(period, len(closes)):
        gains = losses = 0.0
        for j in range(i - period + 1, i + 1):
            d = closes[j] - closes[j - 1]
            gains += max(d, 0.0)
            losses += max(-d, 0.0)
        out[i] = 100.0 if losses == 0 else 100 - 100 / (1 + (gains / losses))
    return out


def rsi2_reversion(bars: list[dict], low: float = 10.0, high: float = 90.0) -> list[float]:
    """Buy 2-period RSI below `low`, sell above `high`, hold one session.

    A classic short-horizon mean-reversion signal, and cheap to falsify.
    """
    closes = [float(b["c"]) for b in bars]
    r = rsi(closes, 2)
    out = []
    for i in range(len(bars) - 1):
        if r[i] is None:
            continue
        move = (closes[i + 1] - closes[i]) / closes[i]
        if r[i] < low:
            out.append(move)
        elif r[i] > high:
            out.append(-move)
    return out


SIGNALS = {
    "overnight (close->open)": overnight,
    "intraday (open->close)": intraday,
    "gap fade": gap_fade,
    "RSI(2) reversion": rsi2_reversion,
}


def atm_spread(rest: AlpacaRest, symbol: str, today: date) -> tuple[float, float] | None:
    """(spread in dollars, spot) for the nearest at-the-money option."""
    try:
        chain = contracts_from_snapshots(
            rest.option_snapshots(symbol, expiry_from=today, expiry_to=today + timedelta(days=9))
        )
    except Exception:  # noqa: BLE001
        return None
    atm = [c for c in chain if c.delta and 0.40 <= abs(c.delta) <= 0.60 and c.bid > 0]
    if not atm:
        return None
    nearest = min(atm, key=lambda c: abs(abs(c.delta) - 0.50))
    return nearest.spread, nearest.strike


def main() -> int:
    symbols = [s.upper() for s in (sys.argv[1:] or ["QQQ", "SPY", "IWM"])]
    rest = AlpacaRest(load_dev_vars(ROOT / ".dev.vars"))
    today = datetime.now(timezone.utc).date()

    print("Signals tested out-of-sample, then charged the friction they would actually pay.")
    print(f"Window {OUT_OF_SAMPLE_FROM} -> {today}. Edge is per contract through a 0.50-delta")
    print("option; friction crosses the real measured ATM spread twice.\n")

    for sym in symbols:
        bars = daily(rest, sym, OUT_OF_SAMPLE_FROM, today)
        if len(bars) < 40:
            print(f"{sym}: only {len(bars)} sessions\n")
            continue
        spread_info = atm_spread(rest, sym, today)
        if not spread_info:
            print(f"{sym}: no ATM quote\n")
            continue
        spread, spot = spread_info
        friction = spread * 100 * 2

        print(f"{sym} — {len(bars)} sessions, ATM spread ${spread:.2f} -> ${friction:.2f} round trip")
        for name, fn in SIGNALS.items():
            rets = fn(bars)
            if len(rets) < 20:
                print(f"   {name:<24} only {len(rets)} trades")
                continue
            mean = statistics.mean(rets)
            sd = statistics.pstdev(rets) or 1e-9
            t = mean / (sd / len(rets) ** 0.5)
            hit = sum(1 for r in rets if r > 0) / len(rets)
            # per contract, through a 0.50-delta option on ~$spot of underlying
            per_contract = mean * spot * 0.50 * 100
            net = per_contract - friction
            verdict = "CLEARS" if net > 0 and t > 1.5 else ("edge<friction" if net <= 0 else "not significant")
            print(
                f"   {name:<24} n={len(rets):>3} mean {mean:+.3%} hit {hit:.0%} t={t:+5.2f} "
                f"| ${per_contract:+7.2f}/contract vs ${friction:.2f} = ${net:+7.2f}  {verdict}"
            )
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
