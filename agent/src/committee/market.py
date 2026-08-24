"""Market snapshot — one immutable view of the world per cycle.

Every role in a cycle argues about the SAME snapshot. This is not a performance
optimisation; it is a correctness requirement learned the hard way. The first live Bear
turn was handed deltas fetched earlier in the session and correctly pointed out they no
longer matched the market — it argued about a trade that no longer existed. If the
structure is built from one fetch and debated against another, the committee is not
reasoning about a real position.

Fetching happens over Alpaca's REST API rather than MCP. MCP returns text shaped for a
model to read; the deterministic layer wants parsed JSON, and the two roles are different.
The agents themselves use MCP throughout — that is where the hackathon's MCP requirement is
satisfied, and where it belongs.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .chain import Contract, contracts_from_snapshots
from .gates import OpenPosition, PortfolioState


def load_dev_vars(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


class AlpacaRest:
    def __init__(self, env: dict[str, str]) -> None:
        self._trade = env["ALPACA_PAPER_ENDPOINT"].rstrip("/")
        self._data = env["ALPACA_DATA_ENDPOINT"].rstrip("/")
        self._headers = {
            "APCA-API-KEY-ID": env["ALPACA_API_KEY_ID"],
            "APCA-API-SECRET-KEY": env["ALPACA_API_SECRET_KEY"],
            # Cloudflare fronts these endpoints and rejects the default urllib agent.
            "User-Agent": "alpaca-committee/0.1",
        }

    def _get(self, url: str) -> dict[str, Any]:
        req = urllib.request.Request(url, headers=self._headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)

    def account(self) -> dict[str, Any]:
        return self._get(f"{self._trade}/account")

    def clock(self) -> dict[str, Any]:
        return self._get(f"{self._trade}/clock")

    def positions(self) -> list[dict[str, Any]]:
        return self._get(f"{self._trade}/positions")  # type: ignore[return-value]

    def option_snapshots(self, underlying: str, limit: int = 1000) -> dict[str, Any]:
        return self._get(
            f"{self._data}/v1beta1/options/snapshots/{underlying}"
            f"?feed=indicative&limit={limit}"
        )

    def latest_stock_quote(self, symbols: str) -> dict[str, Any]:
        return self._get(f"{self._data}/v2/stocks/quotes/latest?symbols={symbols}&feed=iex")


@dataclass(frozen=True)
class MarketSnapshot:
    taken_at: datetime
    is_open: bool
    next_open: str | None
    portfolio: PortfolioState
    chains: dict[str, tuple[Contract, ...]] = field(default_factory=dict)
    spot: dict[str, float] = field(default_factory=dict)

    @property
    def today(self) -> date:
        return self.taken_at.date()

    def chain(self, underlying: str) -> tuple[Contract, ...]:
        return self.chains.get(underlying.upper(), ())

    def describe(self, underlying: str) -> str:
        """Compact, model-readable summary of one underlying.

        Deliberately terse. The first Bear turn consumed ~132k input tokens because raw
        chain payloads reached the model; the deterministic layer has already parsed the
        chain, so the model needs the shape of it, not the dump.
        """
        chain = self.chain(underlying)
        with_greeks = [c for c in chain if c.delta is not None]
        expiries = sorted({c.expiry for c in with_greeks})[:4]
        spot = self.spot.get(underlying.upper())
        lines = [
            f"{underlying}: spot {spot if spot else 'n/a'}, "
            f"{len(chain)} contracts ({len(with_greeks)} with greeks)",
            f"  near expiries: {', '.join(e.isoformat() for e in expiries) or 'none'}",
        ]
        for e in expiries[:2]:
            same = [c for c in with_greeks if c.expiry == e]
            ivs = [c.implied_volatility for c in same if c.implied_volatility]
            if ivs:
                lines.append(
                    f"  {e}: {len(same)} strikes, IV {min(ivs):.1%}-{max(ivs):.1%} "
                    f"(median {sorted(ivs)[len(ivs) // 2]:.1%})"
                )
        return "\n".join(lines)


def _positions_to_state(account: dict[str, Any], raw: list[dict[str, Any]]) -> PortfolioState:
    """Collapse broker legs into committee positions.

    Alpaca reports one row per option leg. A four-leg condor is ONE decision, not four
    positions — counting legs would blow through max_concurrent_positions after two trades
    and is the same category of error that once turned 15 decisions into 72 "trades".
    Legs are grouped by (underlying, expiry).
    """
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for p in raw:
        symbol = p.get("symbol", "")
        underlying = "".join(ch for ch in symbol[:6] if ch.isalpha()) or symbol
        # OCC symbols embed YYMMDD after the root; fall back to the symbol for equities.
        expiry_key = symbol[len(underlying) : len(underlying) + 6] if len(symbol) > 15 else "equity"
        grouped.setdefault((underlying, expiry_key), []).append(p)

    positions: list[OpenPosition] = []
    for (underlying, expiry_key), legs in grouped.items():
        # Worst case for a defined-risk group is unknown from the position endpoint alone;
        # use cost basis as a conservative stand-in until the decision log supplies the
        # structure's recorded max_loss.
        risk = sum(abs(float(l.get("cost_basis", 0.0))) for l in legs)
        try:
            expiry = datetime.strptime(expiry_key, "%y%m%d").date()
        except ValueError:
            expiry = date.max
        positions.append(
            OpenPosition(
                underlying=underlying,
                strategy=f"{len(legs)}-leg",
                fingerprint=f"{underlying}|{expiry_key}",
                max_loss=risk,
                expiry=expiry,
            )
        )

    return PortfolioState(
        equity=float(account["equity"]),
        cash=float(account["cash"]),
        buying_power=float(account["buying_power"]),
        realized_pnl_today=float(account["equity"]) - float(account.get("last_equity", account["equity"])),
        open_positions=tuple(positions),
    )


def take_snapshot(rest: AlpacaRest, underlyings: list[str]) -> MarketSnapshot:
    account = rest.account()
    clock = rest.clock()
    raw_positions = rest.positions()

    chains: dict[str, tuple[Contract, ...]] = {}
    spot: dict[str, float] = {}
    for u in underlyings:
        u = u.upper()
        try:
            chains[u] = tuple(contracts_from_snapshots(rest.option_snapshots(u)))
        except urllib.error.HTTPError as exc:
            chains[u] = ()
            print(f"  !! {u} chain fetch failed: {exc.code}")
        try:
            quotes = rest.latest_stock_quote(u).get("quotes", {}).get(u, {})
            bid, ask = float(quotes.get("bp", 0)), float(quotes.get("ap", 0))
            if bid and ask:
                spot[u] = round((bid + ask) / 2, 2)
        except Exception:  # noqa: BLE001 — spot is nice to have, not required
            pass

    return MarketSnapshot(
        taken_at=datetime.now(timezone.utc),
        is_open=bool(clock.get("is_open")),
        next_open=clock.get("next_open"),
        portfolio=_positions_to_state(account, raw_positions),
        chains=chains,
        spot=spot,
    )
