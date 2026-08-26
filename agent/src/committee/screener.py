"""Find the underlyings worth trading, instead of assuming them.

Until now the universe was three tickers hardcoded on day one — QQQ, SPY, IWM — chosen for
liquid option chains before anything had been measured. The scouts were called scouts but
never scouted: the premium scout made **zero tool calls** in a live cycle, because it was
handed a three-name summary and asked to pick from it.

That put a ceiling on the whole system. The regime read says IWM premium is rich at 1.47x
implied-to-actual. Whether some other liquid name sits at 1.8x was simply never asked.

So: **screen for measured edge.** Pull what is actually moving and actually liquid, keep only
the names whose option chains can genuinely be traded, run the regime read on each, and rank
by the statistic that decides — the breach rate.

⚠️ The filter that matters most is **option liquidity, not stock interest.** The lesson from
news-momentum day trading (Warrior-style small-cap gappers) does not transfer to an options
book: a low-float runner has wide, thin, sometimes non-existent weeklies. We measured TSLA's
26-cent ATM spread destroying a real edge — a small cap is far worse. The catalyst principle
transfers; the instrument does not.

Deterministic throughout. The screener finds candidates; the committee argues about them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Sequence

from .chain import Contract, contracts_from_snapshots
from .regime import Regime, RegimeRead, classify

# Screening costs an API round trip and a chain fetch per name, so the funnel is deliberately
# narrow: take the most active handful, then reject hard on option quality.
MAX_SCREENED = 12
MIN_TRADABLE_STRIKES = 8  # fewer than this and delta selection has nothing to choose from
MAX_ATM_SPREAD_PCT = 0.06  # an ATM spread wider than this eats any edge we could measure
MIN_DTE, MAX_DTE = 1, 12

# ⚠️ EVENT GUARD. The volatility risk premium is a modest, persistent overpricing — the sort
# that shows up as 1.2-1.6x implied-to-realised. When implied runs far beyond that, the market
# is not overpaying for risk; it KNOWS something specific is coming that the historical
# distribution cannot see.
#
# On its first live run this screener ranked NVDA best in the market: breach rate 0%, implied
# 2-day move 8.88%. NVDA reported earnings that afternoon. A backward-looking breach rate
# cannot see a scheduled binary, and selling into one is picking up pennies in front of exactly
# the tail the Bear spends its turns warning about.
#
# So an extreme ratio is a DISQUALIFIER, not a strong buy signal. The screener rejects it
# rather than ranking it first.
EVENT_PREMIUM_RATIO = 2.5


@dataclass(frozen=True)
class Candidate:
    symbol: str
    regime: RegimeRead
    tradable_strikes: int
    atm_spread_pct: float
    expiry: date | None
    reason: str  # why it surfaced: volume, mover, or seed

    @property
    def rank_key(self) -> float:
        """Lower is better. Breach rate is the edge; ties break on tighter options.

        Ranking on the breach rate rather than on the IV/RV ratio is deliberate — it is the
        statistic that compares like with like, and ranking on the wrong one is what put the
        agent on the only fairly-priced name in its universe for two days.
        """
        breach = self.regime.breach_rate if self.regime.breach_rate is not None else 1.0
        return breach + self.atm_spread_pct

    def describe(self) -> str:
        return (
            f"{self.symbol} ({self.reason}): {self.tradable_strikes} tradable strikes, "
            f"ATM spread {self.atm_spread_pct:.1%} — {self.regime.explain()}"
        )


def _chain_quality(chain: Sequence[Contract], expiry: date) -> tuple[int, float]:
    """How tradeable is this expiry? Returns (usable strikes, ATM spread as a fraction)."""
    usable = [
        c
        for c in chain
        if c.expiry == expiry and c.delta is not None and c.bid > 0 and 0.08 <= abs(c.delta) <= 0.45
    ]
    atm = [c for c in chain if c.expiry == expiry and c.delta and 0.40 <= abs(c.delta) <= 0.60 and c.bid > 0]
    if not atm:
        return len(usable), float("inf")
    nearest = min(atm, key=lambda c: abs(abs(c.delta) - 0.50))
    return len(usable), nearest.spread_pct


def screen(
    rest,
    today: date,
    *,
    seeds: Sequence[str] = (),
    limit: int = MAX_SCREENED,
) -> list[Candidate]:
    """Rank underlyings by measured premium edge, subject to option liquidity.

    `seeds` are always considered regardless of what the screener surfaces — so a known-good
    universe never disappears because a screener endpoint had a bad morning.
    """
    symbols: dict[str, str] = {s.upper(): "seed" for s in seeds}

    # Most active by volume: a proxy for "options on this will actually be quoted".
    try:
        payload = rest._get(f"{rest._data}/v1beta1/screener/stocks/most-actives?by=volume&top=25")
        for row in payload.get("most_actives", []) or []:
            sym = str(row.get("symbol", "")).upper()
            if sym and sym not in symbols:
                symbols[sym] = "most active"
    except Exception as exc:  # noqa: BLE001
        print(f"  !! most-actives screen failed: {type(exc).__name__}: {exc}")

    # Movers: where a catalyst has already shown up in the tape.
    try:
        payload = rest._get(f"{rest._data}/v1beta1/screener/stocks/movers?top=15")
        for key in ("gainers", "losers"):
            for row in payload.get(key, []) or []:
                sym = str(row.get("symbol", "")).upper()
                if sym and sym not in symbols:
                    symbols[sym] = f"mover ({key[:-1]}, {float(row.get('percent_change', 0)):+.1f}%)"
    except Exception as exc:  # noqa: BLE001
        print(f"  !! movers screen failed: {type(exc).__name__}: {exc}")

    out: list[Candidate] = []
    for sym, reason in list(symbols.items())[: limit + len(seeds)]:
        try:
            chain = contracts_from_snapshots(
                rest.option_snapshots(
                    sym, expiry_from=today + timedelta(days=MIN_DTE), expiry_to=today + timedelta(days=MAX_DTE)
                )
            )
        except Exception:  # noqa: BLE001 — a name with no options simply drops out
            continue
        if not chain:
            continue

        expiries = sorted({c.expiry for c in chain if c.expiry > today})
        if not expiries:
            continue
        expiry = expiries[0]

        strikes, spread = _chain_quality(chain, expiry)
        # Reject on option quality BEFORE measuring edge: an edge you cannot trade at a
        # sane price is not an edge, and measuring it just invites someone to act on it.
        if strikes < MIN_TRADABLE_STRIKES or spread > MAX_ATM_SPREAD_PCT:
            continue

        atm = [c for c in chain if c.expiry == expiry and c.delta and 0.40 <= abs(c.delta) <= 0.60 and c.implied_volatility]
        if not atm:
            continue
        iv = min(atm, key=lambda c: abs(abs(c.delta) - 0.50)).implied_volatility

        try:
            closes = [float(b["c"]) for b in rest.daily_bars(sym, sessions=70) if b.get("c")]
        except Exception:  # noqa: BLE001
            continue

        read = classify(sym, iv, (expiry - today).days, closes)
        if read.regime is Regime.UNKNOWN:
            continue

        # Reject event premium. The cheapest reliable tell that a binary is coming is that
        # implied has detached from anything the underlying has actually done.
        ratio = read.ratio
        if ratio is not None and ratio > EVENT_PREMIUM_RATIO:
            print(
                f"  -- {sym} rejected: implied {read.implied_move:.1%} is {ratio:.1f}x its own "
                f"realised move. That is an event premium, not a risk premium."
            )
            continue

        out.append(Candidate(sym, read, strikes, spread, expiry, reason))

    out.sort(key=lambda c: c.rank_key)
    return out


def sellable(candidates: Sequence[Candidate]) -> list[Candidate]:
    return [c for c in candidates if c.regime.regime is Regime.PREMIUM_RICH]


def buyable(candidates: Sequence[Candidate]) -> list[Candidate]:
    return [c for c in candidates if c.regime.regime is Regime.PREMIUM_CHEAP]
