"""Option chain model and contract selection.

Deterministic. No model calls. This is the "clear, testable strategy" half of the system —
the LLM committee adjudicates between candidates this module produces, it never invents
strikes of its own.

Data comes from Alpaca's option snapshots endpoint:

    GET {data}/v1beta1/options/snapshots/{underlying}?feed=indicative&limit=1000

`feed=indicative` is free and carries `greeks` and `impliedVolatility`. Note that deep
in-the-money contracts come back WITHOUT a greeks block — a small sample can look exactly
like "greeks are a paid feature". They are not; widen the sample. See docs/AUDIT.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Iterable, Sequence

from .gates import Right

OCC_RE = re.compile(r"^(?P<root>[A-Z]+)(?P<yy>\d{2})(?P<mm>\d{2})(?P<dd>\d{2})(?P<right>[CP])(?P<strike>\d{8})$")


class FillAssumption(str, Enum):
    """How to price a structure when deciding whether it is worth doing.

    CONSERVATIVE crosses the spread on every leg — sell at the bid, buy at the ask. That is
    the worst realistic fill, and it is the default deliberately: paper fills flatter you,
    and a strategy that only clears its thresholds at mid is a strategy that will not clear
    them live. MID is available for comparison and reporting, never for the go/no-go call.
    """

    CONSERVATIVE = "conservative"
    MID = "mid"


@dataclass(frozen=True)
class Contract:
    symbol: str
    underlying: str
    expiry: date
    right: Right
    strike: float
    bid: float
    ask: float
    delta: float | None = None
    implied_volatility: float | None = None
    open_interest: int | None = None

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    @property
    def spread_pct(self) -> float:
        """Spread as a fraction of mid. Infinite when mid is zero — an untradeable quote."""
        m = self.mid
        return float("inf") if m <= 0 else self.spread / m

    def dte(self, today: date) -> int:
        return (self.expiry - today).days

    def price_to_sell(self, assumption: FillAssumption) -> float:
        return self.bid if assumption is FillAssumption.CONSERVATIVE else self.mid

    def price_to_buy(self, assumption: FillAssumption) -> float:
        return self.ask if assumption is FillAssumption.CONSERVATIVE else self.mid


def parse_occ_symbol(symbol: str) -> tuple[str, date, Right, float] | None:
    """QQQ260826P00696000 -> ("QQQ", date(2026,8,26), Right.PUT, 696.0)

    Returns None for anything that isn't a well-formed OCC option symbol, so a stray
    equity ticker in a payload is skipped rather than crashing the run.
    """
    m = OCC_RE.match(symbol)
    if not m:
        return None
    g = m.groupdict()
    try:
        expiry = date(2000 + int(g["yy"]), int(g["mm"]), int(g["dd"]))
    except ValueError:
        return None
    right = Right.CALL if g["right"] == "C" else Right.PUT
    return g["root"], expiry, right, int(g["strike"]) / 1000


def contracts_from_snapshots(payload: dict) -> list[Contract]:
    """Parse Alpaca's `/options/snapshots/{underlying}` response.

    Contracts missing a quote or missing greeks are still returned (with delta=None) —
    filtering is the caller's job, and silently dropping them here would hide how much of
    the chain is actually usable.
    """
    out: list[Contract] = []
    for symbol, snap in (payload.get("snapshots") or {}).items():
        parsed = parse_occ_symbol(symbol)
        if parsed is None:
            continue
        underlying, expiry, right, strike = parsed
        quote = snap.get("latestQuote") or {}
        greeks = snap.get("greeks") or {}
        bid = float(quote.get("bp") or 0.0)
        ask = float(quote.get("ap") or 0.0)
        out.append(
            Contract(
                symbol=symbol,
                underlying=underlying,
                expiry=expiry,
                right=right,
                strike=strike,
                bid=bid,
                ask=ask,
                delta=(float(greeks["delta"]) if "delta" in greeks else None),
                implied_volatility=(
                    float(snap["impliedVolatility"]) if snap.get("impliedVolatility") is not None else None
                ),
            )
        )
    return out


@dataclass(frozen=True)
class LiquidityFilter:
    """Rejects contracts we should not trade regardless of how attractive the delta is.

    A structure is only as good as its worst leg — a beautiful 16-delta short paired with
    an unquotable wing is not a trade.
    """

    min_bid: float = 0.02
    max_spread_pct: float = 0.25
    require_greeks: bool = True

    def accepts(self, c: Contract) -> bool:
        if c.bid < self.min_bid or c.ask <= 0:
            return False
        if c.ask < c.bid:  # crossed/stale quote
            return False
        if c.spread_pct > self.max_spread_pct:
            return False
        if self.require_greeks and c.delta is None:
            return False
        return True


def usable(contracts: Iterable[Contract], liquidity: LiquidityFilter) -> list[Contract]:
    return [c for c in contracts if liquidity.accepts(c)]


def expiries_within(
    contracts: Sequence[Contract], today: date, min_dte: int, max_dte: int
) -> list[date]:
    """Distinct expiries inside the DTE window, nearest first."""
    found = {c.expiry for c in contracts if min_dte <= c.dte(today) <= max_dte}
    return sorted(found)


def select_by_delta(
    contracts: Sequence[Contract],
    right: Right,
    expiry: date,
    target_delta: float,
) -> Contract | None:
    """Contract whose delta is closest to `target_delta`.

    Put deltas are negative in Alpaca's payload; pass the signed target you actually want
    (e.g. -0.16 for a 16-delta short put) so the comparison is unambiguous. Ties break
    toward the further-out-of-the-money strike, which is the safer side of a tie for a
    short leg.
    """
    pool = [c for c in contracts if c.right is right and c.expiry == expiry and c.delta is not None]
    if not pool:
        return None
    further_otm = (lambda c: -c.strike) if right is Right.PUT else (lambda c: c.strike)
    return min(pool, key=lambda c: (abs(c.delta - target_delta), further_otm(c)))


def select_wing(
    contracts: Sequence[Contract],
    right: Right,
    expiry: date,
    short_strike: float,
    wing_width: float,
) -> Contract | None:
    """The protective long leg `wing_width` further out of the money than the short.

    Falls back to the nearest available strike beyond the short when the exact width is
    not listed — chains are not always evenly spaced, and refusing to trade because a
    strike is missing costs more than a slightly different wing.
    """
    target = short_strike - wing_width if right is Right.PUT else short_strike + wing_width
    pool = [
        c
        for c in contracts
        if c.right is right
        and c.expiry == expiry
        and (c.strike < short_strike if right is Right.PUT else c.strike > short_strike)
    ]
    if not pool:
        return None
    return min(pool, key=lambda c: abs(c.strike - target))
