"""ONE battery, run ONCE, reported ONCE. The antidote to serial false confidence.

⭐ WHY THIS EXISTS. Two strategies were evaluated on this project by testing sequentially and
announcing each intermediate result as though it were the verdict. The announcements went:

    RSI(2)      "t=+3.74, strong"        -> DEAD (negative in 9 of 11 years)
    gap-and-go  "survives 11 years"      -> DEAD (edge exactly 0 once you cross the spread)

Neither reversal was random. **Every one moved the same way: more realism, worse result.** So
the failure was not judgment, it was procedure — each check was run only after the previous
one had already been reported as good news. Running them together would have produced one
verdict instead of four.

⚠️ **The asymmetry that governs all of this:** a NEGATIVE result at realistic costs is robust
— if it loses money when charged honestly, that stands. A POSITIVE result is never proof, only
"has not failed yet". So the prior is DEAD until every check passes, and even then the claim
is provisional.

THE BATTERY — a strategy is not evaluated until all of these have run:

  1. FULL HISTORY, not a window.        6 months killed nothing; 11 years killed RSI(2).
  2. OUT-OF-SAMPLE IN TIME.             Different assets in the SAME period is cross-sectional
                                        novelty, not temporal. Only time counts.
  3. SURVIVORSHIP.                      Include delisted names or the losers are deleted.
  4. PER-SETUP MEASURED FRICTION.       A median spread is not a per-setup spread. The
                                        gap-and-go edge lived ENTIRELY in the widest quintile.
  5. REALISTIC FILL.                    A marketable order CROSSES the spread. Mid-fill
                                        assumptions turned $1/day into $205/day.
  6. MULTIPLE-TESTING CORRECTION.       216 tests produced 13 hits where noise predicts 11.
  7. THE FEED YOU WILL ACTUALLY TRADE.  Backtests used SIP; live is IEX at ~2% of volume.
  8. TAIL / VARIANCE.                   A mean is not a paycheck: 43% losing days, and the
                                        worst day is what actually ends an account.

Anything that fails a check is reported as dead. Nothing is announced until every check has
run.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Callable, Sequence


@dataclass
class Check:
    name: str
    passed: bool | None  # None = could not be run, which is NOT a pass
    detail: str

    @property
    def mark(self) -> str:
        return {True: "PASS", False: "FAIL", None: "NOT RUN"}[self.passed]


@dataclass
class Verdict:
    strategy: str
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, passed: bool | None, detail: str) -> None:
        self.checks.append(Check(name, passed, detail))

    @property
    def alive(self) -> bool:
        """Dead unless EVERY check passed. 'Not run' is not a pass."""
        return bool(self.checks) and all(c.passed is True for c in self.checks)

    def report(self) -> str:
        lines = [f"\n{'='*78}", f"{self.strategy}", "=" * 78]
        for c in self.checks:
            lines.append(f"  [{c.mark:^7}] {c.name}")
            lines.append(f"            {c.detail}")
        lines.append("-" * 78)
        if self.alive:
            lines.append("  VERDICT: survives every check. Provisional — 'has not failed yet',")
            lines.append("           never 'works'. Trade small and measure the decay.")
        else:
            failed = [c.name for c in self.checks if c.passed is False]
            missing = [c.name for c in self.checks if c.passed is None]
            lines.append(f"  VERDICT: DEAD. failed={failed or '-'}  not-run={missing or '-'}")
        return "\n".join(lines)


def t_stat(returns: Sequence[float]) -> tuple[float, float, int]:
    """(mean, t, n). The single number every check reduces to."""
    n = len(returns)
    if n < 2:
        return 0.0, 0.0, n
    m = statistics.mean(returns)
    sd = statistics.pstdev(returns) or 1e-12
    return m, m / (sd / n**0.5), n


def benjamini_hochberg(p_values: Sequence[float], q: float = 0.10) -> int:
    """How many discoveries survive an FDR correction. Returns 0 when none do."""
    ordered = sorted(p_values)
    m = len(ordered)
    k = 0
    for i, p in enumerate(ordered, 1):
        if p <= q * i / m:
            k = i
    return k


def survives_full_history(by_year: dict[int, float], min_years: int = 8) -> Check:
    """Positive in most years, across as much history as the data allows."""
    if len(by_year) < min_years:
        return Check("full history", None, f"only {len(by_year)} years available; need {min_years}")
    pos = sum(1 for v in by_year.values() if v > 0)
    ok = pos >= 0.7 * len(by_year)
    return Check(
        "full history",
        ok,
        f"positive in {pos}/{len(by_year)} years "
        f"({'RSI(2) managed 2/11 and looked excellent over 6 months' if not ok else 'consistent'})",
    )


def survives_realistic_fill(
    returns_at: Callable[[float], Sequence[float]],
    *,
    mid: float = 0.5,
    cross: float = 1.0,
) -> Check:
    """⚠️ THE check that killed gap-and-go. A marketable order crosses the spread.

    `returns_at(multiple)` must charge each trade `multiple x ITS OWN measured spread` — not a
    median, and not a constant. Passing requires the edge to survive CROSSING, because that is
    what an order that actually fills does.
    """
    m_mid, t_mid, _ = t_stat(returns_at(mid))
    m_cross, t_cross, n = t_stat(returns_at(cross))
    ok = m_cross > 0 and t_cross > 1.96
    return Check(
        "realistic fill (crosses the spread)",
        ok,
        f"n={n}  at mid {m_mid:+.3f} (t={t_mid:+.2f})  CROSSING {m_cross:+.3f} (t={t_cross:+.2f})"
        + ("" if ok else "  <- edge requires price improvement it cannot count on"),
    )


def concentration_of_edge(returns: Sequence[float], buckets: Sequence[Sequence[float]]) -> Check:
    """Is the edge spread across the sample, or hiding in one corner of it?

    Gap-and-go's entire result sat in the widest-spread quintile (+0.332R) while the other 80%
    of setups returned +0.027R — and that quintile is exactly where the fill model is least
    trustworthy. An edge concentrated where execution is hardest is not an edge.
    """
    stats = [t_stat(b) for b in buckets if len(b) > 20]
    if len(stats) < 3:
        return Check("edge is not concentrated", None, "too few buckets to judge")
    means = [s[0] for s in stats]
    total = sum(m * s[2] for m, s in zip(means, stats))
    best = max(means)
    best_share = best * max(s[2] for s in stats) / total if total else 1.0
    ok = best_share < 0.6
    return Check(
        "edge is not concentrated",
        ok,
        f"strongest bucket carries {best_share:.0%} of the total edge"
        + ("" if ok else "  <- the strategy IS that bucket, not the rule"),
    )


def tail_is_survivable(daily: Sequence[float], equity: float, max_dd_pct: float = 0.15) -> Check:
    """A mean is not a paycheck. The worst day and the drawdown are what end an account."""
    if len(daily) < 30:
        return Check("survivable tail", None, f"only {len(daily)} days")
    eq = peak = 0.0
    mdd = 0.0
    for x in daily:
        eq += x
        peak = max(peak, eq)
        mdd = min(mdd, eq - peak)
    losing = sum(1 for x in daily if x < 0) / len(daily)
    ok = abs(mdd) < equity * max_dd_pct
    return Check(
        "survivable tail",
        ok,
        f"maxDD ${mdd:,.0f} ({abs(mdd)/equity:.1%} of equity), worst day ${min(daily):,.0f}, "
        f"{losing:.0%} of days losing",
    )
