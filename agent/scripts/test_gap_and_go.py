"""Falsify the Ross-Cameron small-cap gap-and-go, market-wide and survivorship-free.

Momentum day trading is the most popular retail strategy there is, so the interesting
question is not "does it work" but "what does it cost to collect". This answers that with
one number: **the slippage at which the edge dies.** Everything else is machinery.

Method, in the order it matters:

1. **Universe is the entire market, not a watchlist.** All ~11k tradable US equities, plus
   the ~2k INACTIVE ones — a small-cap backtest built only from names that still exist is
   biased upward by exactly the pump-and-dumps that later delisted. Both are scanned.
2. **SIP, not IEX.** IEX carries a few percent of volume; a low-float runner is invisible in
   it. The gap and relative-volume filters are meaningless on a fragment of the tape.
3. **Out-of-sample.** The window postdates the archived research entirely.
4. **Slippage is swept, not assumed.** A single friction guess would let the author pick the
   answer. Reporting the break-even point instead makes the reader decide.

⚠️ The optimistic assumption that remains: the stop is modelled as filling AT the stop price
plus the same slippage as the entry. On a gapper reversing hard, real stops slip far worse
than entries do — so the true break-even is BELOW the number this prints. Treat the printed
threshold as a ceiling.

⚠️ LULD halts are not modelled at all. These names halt constantly, and a halt that reopens
against the position is strictly worse than anything simulated here.

    .venv/bin/python scripts/test_gap_and_go.py
"""

from __future__ import annotations

import json
import statistics
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from committee.market import AlpacaRest, load_dev_vars  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
START, END = "2026-02-06", "2026-08-27"

# Ross Cameron's stated filters, as close as public data allows. Float is not available from
# Alpaca, so dollar volume and relative volume stand in for "in play".
MIN_GAP = 0.10
PRICE_LO, PRICE_HI = 1.0, 20.0
MIN_DOLLAR_VOLUME = 10_000_000
MIN_RVOL = 5.0

# The setup: 5-minute opening range, enter on the break, stop at the range low, 2:1 target.
# He trades the first pullback discretionarily; this is the mechanical proxy for it.
OR_MINUTES = 5
REWARD_RISK = 2.0


def assets(rest: AlpacaRest, status: str) -> list[str]:
    req = urllib.request.Request(
        f"{rest._trade}/assets?status={status}&asset_class=us_equity", headers=rest._headers
    )
    with urllib.request.urlopen(req, timeout=180) as h:
        raw = json.load(h)
    return sorted(
        a["symbol"]
        for a in raw
        if a.get("exchange") in ("NASDAQ", "NYSE", "ARCA", "AMEX")
        and a["symbol"].isalpha()
        and len(a["symbol"]) <= 5
    )


def find_gappers(rest: AlpacaRest, symbols: list[str], chunk: int = 300) -> list[dict]:
    hist: dict[str, list[dict]] = {}
    for i in range(0, len(symbols), chunk):
        part, page = ",".join(symbols[i : i + chunk]), None
        while True:
            url = (
                f"{rest._data}/v2/stocks/bars?symbols={part}&timeframe=1Day"
                f"&start={START}&end={END}&limit=10000&feed=sip&adjustment=split"
            )
            if page:
                url += f"&page_token={page}"
            try:
                payload = rest._get(url)
            except Exception as exc:  # noqa: BLE001
                print(f"  chunk {i}: {type(exc).__name__}", flush=True)
                break
            for sym, bars in (payload.get("bars") or {}).items():
                hist.setdefault(sym, []).extend(bars)
            page = payload.get("next_page_token")
            if not page:
                break

    out = []
    for sym, bars in hist.items():
        bars.sort(key=lambda b: b["t"])
        vols = [b["v"] for b in bars]
        for j in range(20, len(bars)):
            b, prev = bars[j], bars[j - 1]
            if not prev["c"] or not b["o"]:
                continue
            gap = (b["o"] - prev["c"]) / prev["c"]
            rvol = b["v"] / (statistics.median(vols[max(0, j - 20) : j]) or 1)
            if (
                gap >= MIN_GAP
                and PRICE_LO <= b["o"] <= PRICE_HI
                and b["o"] * b["v"] >= MIN_DOLLAR_VOLUME
                and rvol >= MIN_RVOL
            ):
                out.append({"sym": sym, "date": b["t"][:10], "gap": gap, "rvol": rvol})
    return out


def minute_bars(rest: AlpacaRest, sym: str, day: str) -> list[dict]:
    out, page = [], None
    while True:
        url = (
            f"{rest._data}/v2/stocks/{sym}/bars?timeframe=1Min&start={day}T13:30:00Z"
            f"&end={day}T20:05:00Z&limit=10000&feed=sip&adjustment=split"
        )
        if page:
            url += f"&page_token={page}"
        payload = rest._get(url)
        out += payload.get("bars") or []
        page = payload.get("next_page_token")
        if not page:
            return out


def simulate(bars: list[dict], slippage: float) -> float | None:
    """R-multiple for one setup, or None if the range never broke.

    When a single bar spans both the stop and the target, the STOP is assumed to have hit
    first. Minute bars cannot resolve the ordering, and the conservative reading is the only
    honest one — the alternative silently inflates every result.
    """
    if len(bars) < OR_MINUTES + 5:
        return None
    opening = bars[:OR_MINUTES]
    high = max(b["h"] for b in opening)
    low = min(b["l"] for b in opening)
    if high <= low:
        return None

    for i in range(OR_MINUTES, len(bars)):
        if bars[i]["h"] <= high:
            continue
        entry = high * (1 + slippage)
        risk = entry - low
        if risk <= 0:
            return None
        target = entry + REWARD_RISK * risk
        for b in bars[i:]:
            if b["l"] <= low:
                return (low * (1 - slippage) - entry) / risk
            if b["h"] >= target:
                return (target * (1 - slippage) - entry) / risk
        return (bars[-1]["c"] * (1 - slippage) - entry) / risk
    return None


def main() -> int:
    rest = AlpacaRest(load_dev_vars(ROOT / ".dev.vars"))

    live, dead = assets(rest, "active"), assets(rest, "inactive")
    print(f"universe: {len(live)} active + {len(dead)} delisted\n")

    gappers = find_gappers(rest, live) + find_gappers(rest, dead)
    print(f"{len(gappers)} gapper-days in {START}..{END}\n")

    intraday = []
    for g in gappers:
        try:
            intraday.append(minute_bars(rest, g["sym"], g["date"]))
        except Exception:  # noqa: BLE001
            continue

    print(f"{'slippage':>9} {'n':>6} {'win%':>6} {'meanR':>9} {'t':>7}  verdict")
    for slip in (0.0, 0.001, 0.0025, 0.005, 0.010):
        rs = [r for r in (simulate(b, slip) for b in intraday) if r is not None]
        if len(rs) < 20:
            continue
        mean = statistics.mean(rs)
        sd = statistics.pstdev(rs) or 1e-9
        t = mean / (sd / len(rs) ** 0.5)
        hit = sum(1 for r in rs if r > 0) / len(rs)
        verdict = "PROFITABLE" if mean > 0 and t > 1.96 else ("marginal" if mean > 0 else "LOSES")
        print(f"{slip:>8.2%} {len(rs):>6} {hit:>5.0%} {mean:>+8.3f}R {t:>+6.2f}  {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
