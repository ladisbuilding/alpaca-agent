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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .chain import Contract, contracts_from_snapshots
from .gates import OpenPosition, PortfolioState
from .regime import RegimeRead, classify

# The strikes a premium seller would actually trade. Outside this band the quotes are
# illiquid and their implied vol is noise — see `realized_vol` and `describe` below.
TRADABLE_DELTA_LO = 0.08
TRADABLE_DELTA_HI = 0.45


def realized_vol(closes: list[float], sessions: int = 30) -> float | None:
    """Annualised close-to-close volatility over `sessions`.

    Computed deterministically and handed to the scouts rather than left to them, because a
    scout choosing its own lookback will choose a flattering one. A live nomination cited
    0.47%/day from a 10-session window when the 30-session figure was 0.78%/day — the Bear
    caught it, but the scout should never have been able to make that claim.
    """
    if len(closes) < 3:
        return None
    window = closes[-(sessions + 1) :]
    rets = [
        (window[i] - window[i - 1]) / window[i - 1]
        for i in range(1, len(window))
        if window[i - 1]
    ]
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return (var ** 0.5) * (252 ** 0.5)


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

    def activities(self, activity_type: str = "FILL", page_size: int = 100) -> list[dict[str, Any]]:
        """Account activities — FILLs are what actually happened, as opposed to orders,
        which are only what was asked for."""
        return self._get(
            f"{self._trade}/account/activities/{activity_type}?page_size={page_size}"
        )  # type: ignore[return-value]

    def option_snapshots(
        self,
        underlying: str,
        limit: int = 1000,
        expiry_from: date | None = None,
        expiry_to: date | None = None,
    ) -> dict[str, Any]:
        """Snapshots, optionally restricted to an expiry window.

        ⚠️ Without a window the endpoint returns the NEAREST 1000 contracts, which on a
        liquid name is only 0-3 DTE. That silently starved every strategy with a longer DTE
        window — a directional sleeve asking for 5-15 DTE found nothing and reported
        NO_STRUCTURE, which reads as "no good trade" rather than "no data".
        """
        url = (
            f"{self._data}/v1beta1/options/snapshots/{underlying}"
            f"?feed=indicative&limit={limit}"
        )
        if expiry_from:
            url += f"&expiration_date_gte={expiry_from.isoformat()}"
        if expiry_to:
            url += f"&expiration_date_lte={expiry_to.isoformat()}"
        return self._get(url)

    def latest_stock_quote(self, symbols: str) -> dict[str, Any]:
        return self._get(f"{self._data}/v2/stocks/quotes/latest?symbols={symbols}&feed=iex")

    def daily_bars(self, symbol: str, sessions: int = 40) -> list[dict[str, Any]]:
        """Daily bars going back far enough for a volatility window.

        `limit` alone returns only the most recent bar — Alpaca needs an explicit `start`.
        Calendar days are ~1.5x sessions to cover weekends and holidays.
        """
        start = (datetime.now(timezone.utc) - timedelta(days=int(sessions * 1.6))).date()
        payload = self._get(
            f"{self._data}/v2/stocks/{symbol}/bars"
            f"?timeframe=1Day&start={start.isoformat()}&limit=1000&feed=iex"
        )
        return payload.get("bars", []) or []


@dataclass(frozen=True)
class MarketSnapshot:
    taken_at: datetime
    is_open: bool
    next_open: str | None
    portfolio: PortfolioState
    chains: dict[str, tuple[Contract, ...]] = field(default_factory=dict)
    spot: dict[str, float] = field(default_factory=dict)
    realized: dict[str, float] = field(default_factory=dict)  # annualised, 30 sessions
    # Daily closes per underlying. The regime read needs the actual move distribution over
    # the SAME number of sessions the option has left — a summary statistic cannot give that.
    closes: dict[str, tuple[float, ...]] = field(default_factory=dict)

    @property
    def today(self) -> date:
        return self.taken_at.date()

    def chain(self, underlying: str) -> tuple[Contract, ...]:
        return self.chains.get(underlying.upper(), ())

    def median_tradable_iv(self, underlying: str) -> float | None:
        """Median IV across strikes we would actually trade — never the whole chain."""
        from .market import TRADABLE_DELTA_LO, TRADABLE_DELTA_HI  # local: avoid cycle

        ivs = sorted(
            c.implied_volatility
            for c in self.chain(underlying)
            if c.delta is not None
            and c.implied_volatility
            and TRADABLE_DELTA_LO <= abs(c.delta) <= TRADABLE_DELTA_HI
            and c.bid > 0
        )
        return ivs[len(ivs) // 2] if ivs else None

    def atm_iv(self, underlying: str, expiry: date) -> float | None:
        """At-the-money implied vol on ONE expiry. Must be the expiry actually being traded:
        pricing one horizon against moves from another is the error this replaced."""
        atm = [
            c
            for c in self.chain(underlying)
            if c.expiry == expiry and c.delta and 0.40 <= abs(c.delta) <= 0.60
            and c.implied_volatility and c.bid > 0
        ]
        if not atm:
            return None
        nearest = min(atm, key=lambda c: abs(abs(c.delta) - 0.50))
        return nearest.implied_volatility

    def regime(self, underlying: str, expiry: date | None = None) -> RegimeRead:
        """Regime for the expiry actually being traded. Without one, the nearest tradable
        expiry is used — which is what the income sleeve would reach for anyway."""
        u = underlying.upper()
        if expiry is None:
            candidates = sorted({c.expiry for c in self.chain(u) if c.expiry > self.today})
            if not candidates:
                return classify(u, None, None, ())
            expiry = candidates[0]
        return classify(u, self.atm_iv(u, expiry), (expiry - self.today).days, self.closes.get(u, ()))

    def describe(self, underlying: str) -> str:
        """Compact, model-readable summary of one underlying.

        ⚠️ IV is reported ONLY over strikes a premium seller would actually trade
        (|delta| 0.08–0.45, quoted). Reporting a median across the whole chain was a live
        bug: deep-ITM strikes trading 1–13 contracts carry meaningless IV, which inflated
        the median to 22–24% when the strikes we'd sell priced at 13–16%. Scouts nominated
        on a "3x IV/RV" premise that did not exist, and the Bear killed every one of them.

        Realized vol is supplied here too, over a FIXED 30-session window, so the scout
        compares against a number it did not get to choose.

        Deliberately terse: the first Bear turn burned ~132k input tokens on raw chain
        payloads. The model needs the shape of the chain, not the dump.
        """
        chain = self.chain(underlying)
        u = underlying.upper()
        with_greeks = [c for c in chain if c.delta is not None]
        expiries = sorted({c.expiry for c in with_greeks})[:4]
        spot = self.spot.get(u)
        rv = self.realized.get(u)

        lines = [
            f"{underlying}: spot {spot if spot else 'n/a'}, "
            f"{len(chain)} contracts ({len(with_greeks)} with greeks)",
            f"  realized vol (30 sessions, annualised): "
            + (f"{rv:.1%}" if rv else "unavailable"),
            f"  near expiries: {', '.join(e.isoformat() for e in expiries) or 'none'}",
        ]
        for e in expiries[:2]:
            tradable = [
                c
                for c in with_greeks
                if c.expiry == e
                and c.implied_volatility
                and TRADABLE_DELTA_LO <= abs(c.delta) <= TRADABLE_DELTA_HI
                and c.bid > 0
            ]
            if not tradable:
                lines.append(f"  {e}: no tradable strikes in the 8-45 delta band")
                continue
            ivs = sorted(c.implied_volatility for c in tradable)  # type: ignore[misc]
            median = ivs[len(ivs) // 2]
            read = self.regime(underlying, e)
            verdict = ""
            if read.breach_rate is not None:
                verdict = (
                    f" | implied {read.implied_move:.2%} move, actually exceeded "
                    f"{read.breach_rate:.0%} of the time (fair ~32%) -> {read.regime.value}"
                )
            lines.append(
                f"  {e}: {len(tradable)} tradable strikes (8-45 delta), "
                f"IV {ivs[0]:.1%}-{ivs[-1]:.1%} median {median:.1%}{verdict}"
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

    # ⚠ `buying_power` is the 4x-margin figure ($400k on a $100k account) and is NOT the
    # constraint that binds defined-risk options — those are cash-secured, so
    # `options_buying_power` ($100k) is. Sizing off `buying_power` authorises 4x the
    # intended risk. Found by the Auditor agent on an empty book, before it could do harm.
    options_bp = account.get("options_buying_power")
    binding_bp = float(
        options_bp if options_bp is not None else account.get("cash", account["buying_power"])
    )

    return PortfolioState(
        equity=float(account["equity"]),
        cash=float(account["cash"]),
        buying_power=binding_bp,
        realized_pnl_today=float(account["equity"]) - float(account.get("last_equity", account["equity"])),
        open_positions=tuple(positions),
    )


def take_snapshot(rest: AlpacaRest, underlyings: list[str]) -> MarketSnapshot:
    account = rest.account()
    clock = rest.clock()
    raw_positions = rest.positions()

    chains: dict[str, tuple[Contract, ...]] = {}
    spot: dict[str, float] = {}
    realized: dict[str, float] = {}
    closes_by_symbol: dict[str, tuple[float, ...]] = {}
    for u in underlyings:
        u = u.upper()
        # Two windows, merged: the nearest contracts for income and a calendar's near leg,
        # plus a longer-dated band for directional spreads and a calendar's far leg. One
        # unfiltered call returns only the nearest 1000, which is 0-3 DTE on a liquid name.
        today = datetime.now(timezone.utc).date()
        merged: dict[str, Contract] = {}
        for lo, hi in ((0, 10), (10, 35)):
            try:
                payload = rest.option_snapshots(
                    u,
                    expiry_from=today + timedelta(days=lo),
                    expiry_to=today + timedelta(days=hi),
                )
                for c in contracts_from_snapshots(payload):
                    merged[c.symbol] = c
            except urllib.error.HTTPError as exc:
                print(f"  !! {u} chain fetch {lo}-{hi}d failed: {exc.code}")
        chains[u] = tuple(merged.values())
        if not chains[u]:
            print(f"  !! {u} chain empty")
        try:
            quotes = rest.latest_stock_quote(u).get("quotes", {}).get(u, {})
            bid, ask = float(quotes.get("bp", 0)), float(quotes.get("ap", 0))
            if bid and ask:
                spot[u] = round((bid + ask) / 2, 2)
        except Exception as exc:  # noqa: BLE001 — spot is nice to have, not required
            print(f"  !! {u} spot unavailable: {type(exc).__name__}: {exc}")
        try:
            closes = [float(b["c"]) for b in rest.daily_bars(u, sessions=70) if b.get("c")]
            closes_by_symbol[u] = tuple(closes)
            rv = realized_vol(closes)
            if rv:
                realized[u] = rv
            else:
                print(f"  !! {u} realized vol unavailable: only {len(closes)} closes")
        except Exception as exc:  # noqa: BLE001
            # Loudly. A silent failure here reads downstream as "regime unknown", which looks
            # like a market condition rather than a broken call — this exact swallow hid a
            # TypeError from a renamed parameter.
            print(f"  !! {u} realized vol failed: {type(exc).__name__}: {exc}")

    return MarketSnapshot(
        taken_at=datetime.now(timezone.utc),
        is_open=bool(clock.get("is_open")),
        next_open=clock.get("next_open"),
        portfolio=_positions_to_state(account, raw_positions),
        chains=chains,
        spot=spot,
        realized=realized,
        closes=closes_by_symbol,
    )
