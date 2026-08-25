"""Opening Range Breakout — a signal with measured, out-of-sample edge.

Why this exists: the committee correctly refuses everything the other sleeves produce. Selling
premium is unpaid (IV/RV 1.05–1.22) and buying a spread at mid is fair value, so its expected
value is minus friction. The Bear's phrasing was exact — *"'Mid-based EV is
neutral-to-slightly-positive' is a tautology: the mid IS fair value."*

A directional scout arguing from narrative ("QQQ fell 6 of 7 sessions") gets dismantled every
time, and deserves to be. **What the Bull needs is a measured edge**, and ORB is the only
thing in this project's lineage that has one.

Rules re-implemented from the archived research (`archived-projects/stock-trader`), written
fresh per the project's no-ported-code ruling. Baseline parameters — the ones that were
actually walk-forward validated, NOT the best-of-288 sweep:

    Opening range   high/low of 09:30–10:00 ET
    Entry window    10:00–14:00 ET
    Range filter    0.1% < range < 2.0% of price
    Volume filter   bar volume >= 1.2x the recent average
    Trend filter    EMA9 vs EMA21 must agree with the breakout direction
    Long            close > range high  → stop at range low, target at 1R
    Short           close < range low   → stop at range high, target at 1R
    Trail           move stop to breakeven once 0.5R is reached
    Time stop       15:55 ET
    One entry per direction per day

⚠️ The archived headline of "Sharpe 3.31" is the best of a 288-combination parameter sweep and
was never itself walk-forward validated — selection bias. The defensible figure is the
BASELINE walk-forward: **1.78 in-sample → 1.93 out-of-sample**. These are the baseline rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from typing import Iterable, Sequence

ET = timezone(timedelta(hours=-4))

OPEN_MIN = 9 * 60 + 30
RANGE_END_MIN = 10 * 60
ENTRY_END_MIN = 14 * 60
TIME_STOP_MIN = 15 * 60 + 55


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"


@dataclass(frozen=True)
class Bar:
    t: datetime
    o: float
    h: float
    l: float
    c: float
    v: float

    @property
    def et_minutes(self) -> int:
        et = self.t.astimezone(ET)
        return et.hour * 60 + et.minute

    @property
    def session(self) -> date:
        return self.t.astimezone(ET).date()


@dataclass(frozen=True)
class ORBConfig:
    range_end_min: int = RANGE_END_MIN
    entry_end_min: int = ENTRY_END_MIN
    time_stop_min: int = TIME_STOP_MIN
    min_range_pct: float = 0.001  # below this there is no volatility to break out of
    max_range_pct: float = 0.02  # above this it is a gap day, and the range is unreliable
    volume_ratio: float = 1.2
    reward_risk: float = 1.0  # breakouts fade; 1R is the conservative target
    trail_at: float = 0.5  # move the stop to breakeven at 0.5R
    ema_fast: int = 9
    ema_slow: int = 21
    use_trend_filter: bool = True


@dataclass
class Trade:
    session: date
    direction: Direction
    entry_time: datetime
    entry: float
    stop: float
    target: float
    exit_time: datetime | None = None
    exit: float | None = None
    reason: str | None = None
    # ⚠️ Captured at entry and never mutated. `stop` MOVES when the trade trails to
    # breakeven, which makes abs(entry - stop) zero — so deriving risk from the live stop
    # silently returned None for every trade that went far enough in our favour to trail,
    # dropping the winners from the sample and reporting a catastrophic false negative.
    initial_risk: float = 0.0

    @property
    def r_multiple(self) -> float | None:
        """P&L in units of the risk taken AT ENTRY. Comparable across days and price levels
        in a way raw dollars is not."""
        if self.exit is None or self.initial_risk <= 0:
            return None
        move = (self.exit - self.entry) if self.direction is Direction.LONG else (self.entry - self.exit)
        return move / self.initial_risk


def ema(values: Sequence[float], span: int) -> list[float]:
    if not values:
        return []
    k = 2 / (span + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


@dataclass
class DaySession:
    """One trading day's opening range and entry state."""

    high: float = 0.0
    low: float = float("inf")
    bars: int = 0
    established: bool = False
    taken: set[Direction] = field(default_factory=set)

    @property
    def range(self) -> float:
        return self.high - self.low if self.established else 0.0


def backtest(bars: Iterable[Bar], config: ORBConfig | None = None) -> list[Trade]:
    """Replay the rules over intraday bars. Deterministic, no lookahead.

    Entry is evaluated on a bar's CLOSE and filled at that close; exits are checked against
    the following bars' high/low. Stops are assumed to fill at the stop price, which
    flatters slightly on gaps — noted rather than hidden, since it applies equally to the
    archived results this is being compared against.
    """
    config = config or ORBConfig()
    bars = sorted(bars, key=lambda b: b.t)
    closes = [b.c for b in bars]
    volumes = [b.v for b in bars]
    fast = ema(closes, config.ema_fast)
    slow = ema(closes, config.ema_slow)

    trades: list[Trade] = []
    sessions: dict[date, DaySession] = {}
    open_trade: Trade | None = None

    for i, bar in enumerate(bars):
        day = sessions.setdefault(bar.session, DaySession())
        m = bar.et_minutes

        # ── manage an open position first ─────────────────────────────────────────
        if open_trade is not None:
            risk = open_trade.initial_risk
            if open_trade.direction is Direction.LONG:
                half = open_trade.entry + risk * config.trail_at
                if bar.l <= open_trade.stop:
                    open_trade.exit, open_trade.reason = open_trade.stop, "stop"
                elif bar.h >= open_trade.target:
                    open_trade.exit, open_trade.reason = open_trade.target, "target"
                elif bar.h >= half and open_trade.stop < open_trade.entry:
                    open_trade.stop = open_trade.entry  # trail to breakeven
            else:
                half = open_trade.entry - risk * config.trail_at
                if bar.h >= open_trade.stop:
                    open_trade.exit, open_trade.reason = open_trade.stop, "stop"
                elif bar.l <= open_trade.target:
                    open_trade.exit, open_trade.reason = open_trade.target, "target"
                elif bar.l <= half and open_trade.stop > open_trade.entry:
                    open_trade.stop = open_trade.entry

            if open_trade.exit is None and m >= config.time_stop_min:
                open_trade.exit, open_trade.reason = bar.c, "time_stop"

            if open_trade.exit is not None:
                open_trade.exit_time = bar.t
                trades.append(open_trade)
                open_trade = None
                continue

        # ── build the opening range ───────────────────────────────────────────────
        if OPEN_MIN <= m < config.range_end_min:
            day.high = max(day.high, bar.h)
            day.low = min(day.low, bar.l)
            day.bars += 1
            continue
        if m >= config.range_end_min and not day.established and day.bars > 0:
            day.established = True

        # ── look for an entry ─────────────────────────────────────────────────────
        if open_trade is not None or not day.established:
            continue
        if m < config.range_end_min or m > config.entry_end_min:
            continue

        rng = day.range
        if rng < bar.c * config.min_range_pct or rng > bar.c * config.max_range_pct:
            continue

        window = volumes[max(0, i - 20) : i]
        avg_vol = sum(window) / len(window) if window else 0
        if avg_vol <= 0 or bar.v < avg_vol * config.volume_ratio:
            continue

        bullish = (not config.use_trend_filter) or fast[i] > slow[i]
        bearish = (not config.use_trend_filter) or fast[i] < slow[i]

        if bar.c > day.high and bullish and Direction.LONG not in day.taken:
            risk = bar.c - day.low
            if risk > 0:
                day.taken.add(Direction.LONG)
                open_trade = Trade(
                    bar.session, Direction.LONG, bar.t, bar.c, day.low,
                    bar.c + risk * config.reward_risk, initial_risk=risk,
                )
        elif bar.c < day.low and bearish and Direction.SHORT not in day.taken:
            risk = day.high - bar.c
            if risk > 0:
                day.taken.add(Direction.SHORT)
                open_trade = Trade(
                    bar.session, Direction.SHORT, bar.t, bar.c, day.high,
                    bar.c - risk * config.reward_risk, initial_risk=risk,
                )

    return trades


@dataclass
class Performance:
    trades: int
    wins: int
    losses: int
    total_r: float
    avg_r: float
    sharpe: float | None
    win_rate: float | None
    profit_factor: float | None
    max_drawdown_r: float

    def summary(self) -> str:
        wr = f"{self.win_rate:.1%}" if self.win_rate is not None else "—"
        pf = f"{self.profit_factor:.2f}" if self.profit_factor is not None else "—"
        sh = f"{self.sharpe:.2f}" if self.sharpe is not None else "—"
        return (
            f"{self.trades} trades · win {wr} · total {self.total_r:+.1f}R · "
            f"avg {self.avg_r:+.3f}R · Sharpe {sh} · PF {pf} · maxDD {self.max_drawdown_r:.1f}R"
        )


def evaluate(trades: Sequence[Trade]) -> Performance:
    """Performance in R-multiples.

    R rather than dollars on purpose: it is comparable across price levels and position
    sizes, and it cannot be inflated by choosing a bigger account. Sharpe is annualised from
    per-trade returns at ~5.5 trades/week.
    """
    rs = [t.r_multiple for t in trades if t.r_multiple is not None]
    if not rs:
        return Performance(0, 0, 0, 0.0, 0.0, None, None, None, 0.0)

    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    total = sum(rs)
    avg = total / len(rs)

    sharpe = None
    if len(rs) > 2:
        var = sum((r - avg) ** 2 for r in rs) / (len(rs) - 1)
        sd = var ** 0.5
        if sd > 0:
            sharpe = (avg / sd) * ((5.5 * 52) ** 0.5)

    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    pf = (gross_win / gross_loss) if gross_loss > 0 else None

    equity, peak, max_dd = 0.0, 0.0, 0.0
    for r in rs:
        equity += r
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)

    return Performance(
        trades=len(rs),
        wins=len(wins),
        losses=len(losses),
        total_r=total,
        avg_r=avg,
        sharpe=sharpe,
        win_rate=len(wins) / len(rs),
        profit_factor=pf,
        max_drawdown_r=max_dd,
    )
