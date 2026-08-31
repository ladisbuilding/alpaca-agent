"""THE measurement: do we cross the spread, or get price improvement?

Every strategy tested on this project died on this one unknown — a backtest can only assume
it, and paper trading cannot answer it either because paper fills instantly at the quote.
So this reconciles the quotes captured AT SUBMISSION (cycle.py: quotes_at_submit) against
the prices actually filled, and reports the only number that matters.

    .venv/bin/python scripts/fill_quality.py
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from committee.fills import FillRecord, FillReport  # noqa: E402
from committee.market import AlpacaRest, load_dev_vars  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
API = "https://alpaca-agent-api.domfly.workers.dev"


def main() -> int:
    rest = AlpacaRest(load_dev_vars(ROOT / ".dev.vars"))

    # every leg we have ever filled, keyed by symbol
    fills: dict[str, list[dict]] = {}
    for a in rest.activities("FILL", page_size=100):
        fills.setdefault(str(a.get("symbol")), []).append(a)

    req = urllib.request.Request(f"{API}/cycles?limit=200", headers={"user-agent": "fill-quality/1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            cycles = json.load(r)
    except Exception as exc:  # noqa: BLE001
        print(f"could not read cycle records: {type(exc).__name__}: {exc}")
        return 1

    report = FillReport()
    unmatched = 0
    for c in cycles if isinstance(cycles, list) else cycles.get("cycles", []):
        rec = c.get("record")
        if isinstance(rec, str):
            rec = json.loads(rec)
        for d in (rec or {}).get("deliberations", []):
            quotes = d.get("quotes_at_submit") or {}
            if not quotes:
                continue
            for leg in (d.get("structure") or {}).get("legs", []):
                sym = leg.get("symbol")
                q = quotes.get(sym)
                got = fills.get(sym)
                if not q or not got:
                    unmatched += 1
                    continue
                report.add(
                    FillRecord(
                        symbol=sym,
                        side=str(leg.get("side")),
                        qty=int(leg.get("qty", 1)),
                        bid=float(q["bid"]),
                        ask=float(q["ask"]),
                        fill_price=float(got[0].get("price", 0)),
                    )
                )

    for f in report.measurable:
        print(f"  {f.describe()}")
    print()
    summary = report.summary()
    for k, v in summary.items():
        print(f"  {k:<28} {v}")
    if summary.get("n", 0) < 20:
        print("\n  ⚠️ Under 20 legs. The two condors closed on this account so far returned")
        print("     +$21 and +$12 net — suggestive of price improvement, but n=2 proves")
        print("     nothing. Do not act on this number until the sample is real.")
    if unmatched:
        print(f"  ({unmatched} legs had no captured quote — orders placed before instrumentation)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
