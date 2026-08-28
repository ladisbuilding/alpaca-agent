"""HTTP entrypoint for the container.

The Worker's cron trigger POSTs /cycle; this runs one committee sitting and forwards the
record to the api. The schedule lives in the Worker's wrangler.jsonc rather than in a cron
inside the container, so it is visible in config and changeable without a rebuild.

Configuration is entirely environment variables — the container holds no files of its own
and gets its secrets from the Worker.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import traceback
import urllib.request
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

from .cycle import run_cycle
from .market import AlpacaRest, take_snapshot
from .mcp_client import McpCredentials
from .screener import screen
from .switches import Switches

PORT = int(os.environ.get("PORT", "8080"))

# Cloudflare fronts the api and blocks urllib's default agent with error 1010 (a bot
# signature, not a rate limit) — the symptom is a bare 403 on a request that works from
# curl. Every outbound call from this container sends a real agent string.
UA = "alpaca-committee/0.1 (+https://alpaca-agent.domfly.workers.dev)"

# Daily spend ceiling, checked against the api before a sitting begins. Observed usage is
# ~$25/day; the structural worst case is ~$140. This runs for a week with nobody watching,
# so the gap between those two numbers needs a floor under it, not just an expectation.
# NOTE: this is a soft cap enforced by our own code. The only HARD stop is a spend limit
# set on the key in the Anthropic Console.
DAILY_USD_CAP = float(os.environ.get("DAILY_USD_CAP", "40"))
MAX_CYCLE_USD = float(os.environ.get("MAX_CYCLE_USD", "6"))


def spent_today(api: str | None) -> float:
    """Today's spend, from the api. On failure returns 0.0 — a spend check that cannot
    reach the ledger must not become the reason the agent stops trading. The Console limit
    is the backstop for that case."""
    if not api:
        return 0.0
    try:
        req = urllib.request.Request(f"{api.rstrip('/')}/spend", headers={"user-agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            return float(json.load(r).get("spent_today", 0.0))
    except Exception:  # noqa: BLE001
        return 0.0


def env_config() -> dict[str, str]:
    missing = [
        k
        for k in ("ALPACA_API_KEY_ID", "ALPACA_API_SECRET_KEY", "ANTHROPIC_API_KEY")
        if not os.environ.get(k)
    ]
    if missing:
        raise RuntimeError(f"missing required env: {', '.join(missing)}")
    return {
        "ALPACA_API_KEY_ID": os.environ["ALPACA_API_KEY_ID"],
        "ALPACA_API_SECRET_KEY": os.environ["ALPACA_API_SECRET_KEY"],
        "ALPACA_PAPER_ENDPOINT": os.environ.get(
            "ALPACA_PAPER_ENDPOINT", "https://paper-api.alpaca.markets/v2"
        ),
        "ALPACA_DATA_ENDPOINT": os.environ.get(
            "ALPACA_DATA_ENDPOINT", "https://data.alpaca.markets"
        ),
        "ANTHROPIC_API_KEY": os.environ["ANTHROPIC_API_KEY"],
    }


def post_record(record_json: str) -> tuple[int, str]:
    """Forward the sitting to the api. A failure here must not lose the record — it is
    returned in the response body so the caller still has it."""
    api = os.environ.get("API_ORIGIN")
    if not api:
        return 0, "API_ORIGIN unset — record not forwarded"
    req = urllib.request.Request(
        f"{api.rstrip('/')}/cycles",
        data=record_json.encode(),
        headers={
            "content-type": "application/json",
            "user-agent": UA,
            **(
                {"authorization": f"Bearer {os.environ['INGEST_TOKEN']}"}
                if os.environ.get("INGEST_TOKEN")
                else {}
            ),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()[:200]
    except Exception as exc:  # noqa: BLE001
        return 0, f"{type(exc).__name__}: {exc}"


def open_decisions(api: str | None) -> list[dict]:
    """Executed decisions from prior cycles, so exits can be matched to what opened them.

    Read back from the api rather than held in memory: containers are ephemeral, and one that
    forgets what it opened cannot manage it.
    """
    if not api:
        return []
    out: list[dict] = []
    try:
        req = urllib.request.Request(
            f"{api.rstrip('/')}/cycles?limit=60", headers={"user-agent": UA}
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            cycles = json.load(r).get("cycles", [])
    except Exception as exc:  # noqa: BLE001
        print(f"  !! could not load prior cycles: {type(exc).__name__}: {exc}")
        return []
    for c in cycles:
        try:
            req = urllib.request.Request(
                f"{api.rstrip('/')}/cycles/{c['id']}", headers={"user-agent": UA}
            )
            with urllib.request.urlopen(req, timeout=20) as r:
                rec = json.load(r)
        except Exception:  # noqa: BLE001
            continue
        out += [d for d in rec.get("deliberations", []) if d.get("executed")]
    return out


def recent_fingerprints(api: str | None) -> list[tuple[str, date]]:
    """What we have already traded and is still live.

    Read back from the api rather than held in memory: containers are ephemeral, and a
    restarted container that forgets its own positions would re-enter the same structure.
    That is exactly how a dedup window fails in practice.
    """
    if not api:
        return []
    def _get(url: str):
        return urllib.request.Request(url, headers={"user-agent": UA})

    try:
        with urllib.request.urlopen(_get(f"{api.rstrip('/')}/cycles?limit=40"), timeout=20) as r:
            cycles = json.load(r).get("cycles", [])
    except Exception:  # noqa: BLE001
        return []

    out: list[tuple[str, date]] = []
    for c in cycles:
        try:
            with urllib.request.urlopen(_get(f"{api.rstrip('/')}/cycles/{c['id']}"), timeout=20) as r:
                rec = json.load(r)
        except Exception:  # noqa: BLE001
            continue
        for d in rec.get("deliberations", []):
            s = d.get("structure") or {}
            if d.get("executed") and s.get("fingerprint") and s.get("expiry"):
                out.append((s["fingerprint"], date.fromisoformat(s["expiry"])))
    return out


def _screen_safely(rest, today, seeds):
    """Screening is an enhancement, not a dependency. If it fails the cycle still runs on
    the seed universe rather than standing down because a screener endpoint had a bad day."""
    try:
        return screen(rest, today, seeds=seeds)
    except Exception as exc:  # noqa: BLE001
        print(f"  !! screener failed, falling back to seeds: {type(exc).__name__}: {exc}")
        return []


async def one_cycle(force: bool = False, live: bool | None = None) -> dict:
    env = env_config()
    rest = AlpacaRest(env)
    universe = [u.strip().upper() for u in os.environ.get("UNIVERSE", "QQQ,SPY,IWM").split(",") if u.strip()]

    # Screen FIRST, then snapshot the union — a candidate the scouts cannot see the chain for
    # is a candidate they cannot nominate.
    screened = _screen_safely(rest, datetime.now(timezone.utc).date(), universe)
    universe = list(dict.fromkeys(universe + [c.symbol for c in screened]))[:6]
    snapshot = take_snapshot(rest, universe)

    # A cron firing outside market hours must not spend money on scouts. The gates would
    # block everything anyway, so the LLM work would be pure waste.
    if not snapshot.is_open and not force:
        return {
            "skipped": True,
            "reason": "market closed",
            "next_open": snapshot.next_open,
            "equity": snapshot.portfolio.equity,
        }

    dry_run = (os.environ.get("DRY_RUN", "true").lower() != "false") if live is None else not live
    api = os.environ.get("API_ORIGIN")

    spent = spent_today(api)
    if spent >= DAILY_USD_CAP:
        return {
            "skipped": True,
            "reason": f"daily spend cap reached (${spent:.2f} of ${DAILY_USD_CAP:.2f})",
            "spent_today": round(spent, 2),
            "equity": snapshot.portfolio.equity,
        }

    try:
        broker_positions = rest.positions()
    except Exception as exc:  # noqa: BLE001
        broker_positions = []
        print(f"  !! positions fetch failed: {type(exc).__name__}: {exc}")

    record = await run_cycle(
        snapshot,
        McpCredentials(env["ALPACA_API_KEY_ID"], env["ALPACA_API_SECRET_KEY"], paper=True),
        env["ANTHROPIC_API_KEY"],
        universe=universe,
        dry_run=dry_run,
        kill_switch=os.environ.get("KILL_SWITCH", "false").lower() == "true",
        recent_fingerprints=recent_fingerprints(api),
        max_trades=int(os.environ.get("MAX_TRADES", "2")),
        max_cycle_usd=MAX_CYCLE_USD,
        open_decisions=open_decisions(api),
        broker_positions=broker_positions,
        candidates=screened,
        # Lets the exit path re-read the book from the broker after a close, instead of
        # trusting the closing tool call's output. See the note in cycle.py.
        refetch_positions=rest.positions,
        switches=Switches.parse(
            os.environ.get("STRATEGY_MODES"),
            global_kill=os.environ.get("KILL_SWITCH", "false").lower() == "true",
        ),
    )

    status, body = post_record(record.to_json())
    return {
        "skipped": False,
        "dry_run": dry_run,
        "market_open": record.market_open,
        "nominations": len(record.nominations),
        "deliberations": len(record.deliberations),
        "orders_placed": record.orders_placed,
        "positions_closed": record.positions_closed,
        "exits": record.exits,
        "cost_usd": round(record.cost_usd, 4),
        "spent_today_before": round(spent, 2),
        "daily_cap": DAILY_USD_CAP,
        "forwarded": {"status": status, "body": body},
        "notes": record.notes,
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, default=str).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/health"):
            self._send(200, {"ok": True, "service": "alpaca-committee"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if not self.path.startswith("/cycle"):
            self._send(404, {"error": "not found"})
            return
        force = "force=1" in self.path
        live = True if "live=1" in self.path else None
        try:
            result = asyncio.run(one_cycle(force=force, live=live))
            self._send(200, result)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._send(500, {"error": f"{type(exc).__name__}: {exc}"})

    def log_message(self, fmt: str, *args) -> None:
        # Container logs go to the Worker's tail; keep them one-line and parseable.
        sys.stderr.write(f"[{datetime.now().isoformat()}] {fmt % args}\n")


def main() -> None:
    print(f"committee container listening on :{PORT}", flush=True)
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
