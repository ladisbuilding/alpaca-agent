"""Run one committee cycle.

    .venv/bin/python scripts/run_cycle.py                 # dry run (default)
    .venv/bin/python scripts/run_cycle.py --live          # actually place orders
    .venv/bin/python scripts/run_cycle.py --universe QQQ,SPY,IWM

Dry run is the default and --live is explicit, because the failure mode of getting that
backwards is placing real (paper) orders you did not intend to audit.

Records are written to runs/ as JSON — one file per cycle. That directory is the api's
source of truth and the dashboard's feed.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from committee.cycle import run_cycle  # noqa: E402
from committee.market import AlpacaRest, load_dev_vars, take_snapshot  # noqa: E402
from committee.mcp_client import McpCredentials  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs"
DEFAULT_UNIVERSE = ["QQQ", "SPY", "IWM"]


def recent_fingerprints() -> list[tuple[str, date]]:
    """Fingerprints of structures already traded and still live.

    Read from prior cycle records rather than held in memory, so a restarted container does
    not forget what it already traded and re-enter the same structure. That memory loss is
    precisely how a dedup window fails in practice.
    """
    out: list[tuple[str, date]] = []
    if not RUNS.exists():
        return out
    import json

    for f in sorted(RUNS.glob("cycle-*.json")):
        try:
            rec = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        for d in rec.get("deliberations", []):
            if d.get("executed") and d.get("structure"):
                fp = d["structure"].get("fingerprint")
                exp = d["structure"].get("expiry")
                if fp and exp:
                    out.append((fp, date.fromisoformat(exp)))
    return out


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="place orders (default is dry run)")
    ap.add_argument("--universe", default=",".join(DEFAULT_UNIVERSE))
    ap.add_argument("--kill-switch", action="store_true")
    ap.add_argument("--max-trades", type=int, default=2)
    args = ap.parse_args()

    universe = [u.strip().upper() for u in args.universe.split(",") if u.strip()]
    env = load_dev_vars(ROOT / ".dev.vars")
    rest = AlpacaRest(env)
    creds = McpCredentials.from_dev_vars(ROOT / ".dev.vars")

    print(f"universe: {', '.join(universe)}  mode: {'LIVE' if args.live else 'DRY RUN'}")
    snapshot = take_snapshot(rest, universe)
    print(
        f"snapshot {snapshot.taken_at:%H:%M:%S} UTC  market "
        f"{'OPEN' if snapshot.is_open else 'CLOSED'}  "
        f"equity ${snapshot.portfolio.equity:,.0f}  "
        f"{len(snapshot.portfolio.open_positions)} position(s)"
    )
    for u in universe:
        print("  " + snapshot.describe(u).replace("\n", "\n  "))

    record = await run_cycle(
        snapshot,
        creds,
        env["ANTHROPIC_API_KEY"],
        universe=universe,
        dry_run=not args.live,
        kill_switch=args.kill_switch,
        recent_fingerprints=recent_fingerprints(),
        max_trades=args.max_trades,
    )

    RUNS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = RUNS / f"cycle-{stamp}.json"
    path.write_text(record.to_json())

    print(f"\n{'=' * 72}")
    print(f"nominations : {len(record.nominations)}")
    for n in record.nominations:
        print(f"   {n['underlying']:<6} {n['sleeve']:<12} conv {n['conviction']}  ({n['source']})")
    print(f"deliberations: {len(record.deliberations)}")
    for d in record.deliberations:
        head = f"   {d['nomination']['underlying']:<6} {d['strategy']:<20}"
        print(f"{head} pre-gate: {d['pre_gate']['summary']}")
        for r in d["pre_gate"]["reasons"]:
            print(f"        - {r}")
        if d["debated"]:
            print(f"        bear verdict: {d['bear_verdict']}")
            if d["final_gate"]:
                print(f"        final gate  : {d['final_gate']['summary']}")
            if d["execution_note"]:
                print(f"        execution   : {d['execution_note'][:160]}")
    for note in record.notes:
        print(f"note: {note}")
    print(f"\ntrades placed: {record.trades_placed}   cost: ${record.cost_usd:.2f}")
    cached = sum(t.get("cache_read_tokens", 0) for t in record.turns)
    total_in = sum(t.get("input_tokens", 0) for t in record.turns)
    print(f"tokens in: {total_in:,}  cache reads: {cached:,}")
    print(f"record: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
