"""Discover the Alpaca MCP server's real tool surface, per toolset.

    .venv/bin/python scripts/discover_tools.py

MCP v2 is a complete rewrite — none of the v1 tool names survived. Guessing a tool name
from memory produces a runtime failure at the worst possible moment, so the committee's
role definitions are built from what this script reports, not from documentation.

Also proves the least-privilege claim: a server started without the `trading` toolset must
expose no order-placing tool at all.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[2]
SERVER = str(Path(__file__).resolve().parents[1] / ".venv" / "bin" / "alpaca-mcp-server")

# Roles that must never be able to trade, and the one that must.
SCOPES = {
    "research (scouts, bull, bear, risk officer)": "stock-data,options-data,news,assets,account",
    "executor (post-gate only)": "trading,options-data,assets,account",
    "everything (reference)": None,
}


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    path = ROOT / ".dev.vars"
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


async def tools_for(toolsets: str | None, creds: dict[str, str]) -> list[tuple[str, str]]:
    env = {
        **os.environ,
        "ALPACA_API_KEY": creds["ALPACA_API_KEY_ID"],
        "ALPACA_SECRET_KEY": creds["ALPACA_API_SECRET_KEY"],
        "ALPACA_PAPER_TRADE": "true",
    }
    if toolsets:
        env["ALPACA_TOOLSETS"] = toolsets

    params = StdioServerParameters(command=SERVER, args=["--transport", "stdio"], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            return [(t.name, (t.description or "").split("\n")[0][:90]) for t in listed.tools]


async def main() -> int:
    creds = load_env()
    results: dict[str, list[tuple[str, str]]] = {}

    for label, toolsets in SCOPES.items():
        try:
            found = await tools_for(toolsets, creds)
        except Exception as exc:  # noqa: BLE001
            print(f"!! {label}: {type(exc).__name__}: {exc}")
            return 1
        results[label] = found
        print(f"\n=== {label} ===")
        print(f"toolsets: {toolsets or 'ALL'} -> {len(found)} tools")
        for name, desc in sorted(found):
            print(f"  {name:<42} {desc}")

    # ── the least-privilege assertion ──────────────────────────────────────────────
    research = {n for n, _ in results["research (scouts, bull, bear, risk officer)"]}
    executor = {n for n, _ in results["executor (post-gate only)"]}
    order_tools = {n for n in executor if "order" in n.lower() and "get" not in n.lower()}

    print("\n=== least-privilege check ===")
    leaked = sorted(n for n in research if "order" in n.lower() and "get" not in n.lower())
    print(f"order-placing tools visible to the executor : {sorted(order_tools) or 'NONE (!)'}")
    print(f"order-placing tools visible to research     : {leaked or 'NONE'}")
    if leaked:
        print("\n!! FAIL — research roles can place orders. The toolset scope is not holding.")
        return 1
    if not order_tools:
        print("\n!! FAIL — the executor has no order tool. Wrong toolset name?")
        return 1
    print("\nPASS — advocates physically cannot trade; only the executor can.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
