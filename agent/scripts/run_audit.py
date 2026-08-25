"""Audit the account: what the committee believes it did vs what the broker says happened.

    .venv/bin/python scripts/run_audit.py

Deterministic reconciliation first (committee/audit.py, no model in the loop), then the
Auditor agent reads the report and exercises judgment about what looks wrong. The agent
never computes the numbers — a figure a model can talk itself into is not an audit.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from anthropic import AsyncAnthropic  # noqa: E402

from committee.audit import audit, format_report  # noqa: E402
from committee.llm import run_turn  # noqa: E402
from committee.market import AlpacaRest, load_dev_vars  # noqa: E402
from committee.mcp_client import McpCredentials, scoped_session  # noqa: E402
from committee.roles import AUDITOR  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
UA = "alpaca-committee/0.1"


def executed_decisions(api: str) -> list[dict]:
    """Every decision the committee recorded as executed, from the api."""
    out: list[dict] = []
    try:
        req = urllib.request.Request(f"{api}/cycles?limit=100", headers={"user-agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            cycles = json.load(r).get("cycles", [])
    except Exception as exc:  # noqa: BLE001
        print(f"!! could not reach api: {exc}")
        return out
    for c in cycles:
        try:
            req = urllib.request.Request(f"{api}/cycles/{c['id']}", headers={"user-agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                rec = json.load(r)
        except Exception:  # noqa: BLE001
            continue
        out += [d for d in rec.get("deliberations", []) if d.get("executed")]
    return out


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-agent", action="store_true", help="deterministic report only")
    ap.add_argument("--api", default="https://alpaca-agent-api.domfly.workers.dev")
    args = ap.parse_args()

    env = load_dev_vars(ROOT / ".dev.vars")
    rest = AlpacaRest(env)

    account = rest.account()
    activities = rest.activities("FILL")
    decisions = executed_decisions(args.api)

    # The broker's own unrealized total, so the reconciliation can tell a legitimate open
    # mark apart from a genuinely unexplained gap.
    try:
        unrealized = sum(float(p.get("unrealized_pl", 0) or 0) for p in rest.positions())
    except Exception:  # noqa: BLE001
        unrealized = None

    report = audit(account, activities, decisions, open_unrealized=unrealized)
    print("=" * 76)
    print(format_report(report))
    print("=" * 76)

    if args.no_agent:
        return 0

    client = AsyncAnthropic(api_key=env["ANTHROPIC_API_KEY"])
    creds = McpCredentials.from_dev_vars(ROOT / ".dev.vars")
    prompt = (
        "Deterministic reconciliation of the account follows. You did not compute these\n"
        "numbers and must not recompute them — read them, verify what you can against the\n"
        "broker via your tools, and say what looks wrong.\n\n"
        f"{format_report(report)}\n\n"
        f"Raw: {len(activities)} fill activities, {len(decisions)} executed decisions on record.\n\n"
        "Report: realized and unrealized P&L by strategy, the decision count alongside the raw\n"
        "order count, and an anomalies list. Be hostile to good news."
    )
    async with scoped_session(AUDITOR.toolsets, creds) as (session, schemas):
        print(f"auditor scope: {len(session.tool_names)} tools, "
              f"can place orders = {session.can('place_option_order')}")
        turn = await run_turn(client, AUDITOR, session, schemas, prompt)
    print(f"\n--- AUDITOR ({turn.model}, {len(turn.tool_calls)} tool calls) ---\n")
    print(turn.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
