# Strategy brief — for independent review

> ## ⚠️ UPDATE 2026-08-31 — STRATEGY 1 IS FALSIFIED. DO NOT EVALUATE IT AS LIVE.
>
> After writing this brief I tested RSI(2) on the **full 2016–2026 history** instead of the
> six months below. It **loses money**:
>
> | window | n | mean/trade | t |
> |---|---|---|---|
> | Feb–Aug 2026 (what it was fitted on) | 474 | **+0.231%** | **+4.40** |
> | **FULL 2016–2026** | **10,381** | **−0.013%** | **−1.43** |
>
> **Negative in 9 of 11 years.** 2026 is the best year in the decade and it is the year it was
> measured on. The thin/thick-arbitrage story died with it — over full history thin pools to
> t=−1.43 and thick to t=−1.09, **no difference at all.**
>
> **The error, which is the part worth reviewing:** I called Feb–Aug 2026 "out of sample"
> because my own earlier research ended there. RSI(2) is Connors' published rule from the
> 2000s — out-of-sample relative to your own prior work means nothing for a rule that old.
> And the argument I found most persuasive was empty: *"the hypothesis predicted the pattern,
> then new assets confirmed it"* drew **the prediction and the confirmation from the same 2026
> window.** Different assets in the same period is cross-sectional novelty, not temporal
> novelty. Weakness #1 and #2 below called this out and I proceeded anyway.
>
> **Strategy 2 (gap-and-go) was then put through the same test and SURVIVED:**
> **n=774 sampled across 2016–2026, mean +0.142R, t=+2.94, positive in 10 of 11 years.**
> It is the one worth your attention. Its own caveats are in the updated section below.

**Please try to falsify this, not confirm it.** The numbers below are mine and I already
distrust parts of them; the weaknesses I know about are listed at the end, and I would rather
hear about ones I missed. Where you think I am wrong, say so directly.

Account is **paper** (Alpaca, $100k, simulated funds). Nothing here has traded real money.

---

## Strategy 1 — RSI(2) mean reversion ⚠️ FALSIFIED, retained as the record

**The claim being tested:** short-horizon mean reversion still pays in corners of the market
where arbitrage capital is thin, and is gone where it is thick.

**Rules (complete and reproducible):**
- Universe: `LQD, HYG, TLT, IEF, EFA, EEM, IWM`
- Indicator: 2-period RSI on **daily closes** (Wilder-style gains/losses over 2 bars)
- Entry: `RSI(2) < 10` → **buy** at that day's close; `RSI(2) > 90` → **short** at the close
- Exit: **the next day's close.** Always. No stop, no target, one-day hold.
- Size tested: $20,000 notional per signal
- Friction charged: 4bp round trip

**Measured, 2026-02-06 → 2026-08-30 (~120 trading days):**

| asset | n | mean/trade | hit rate | t |
|---|---|---|---|---|
| LQD | 65 | +0.116% | 65% | +2.95 |
| EFA | 57 | +0.432% | 74% | +2.68 |
| IWM | 68 | +0.309% | 59% | +2.11 |
| HYG | 62 | +0.068% | 68% | +2.10 |
| TLT | 73 | +0.136% | 53% | +2.06 |
| EEM | 79 | +0.471% | 62% | +1.92 |
| IEF | 70 | +0.067% | 59% | +1.61 |

Pooled: **thin-arbitrage group (bonds/EM/small) n=951, mean +0.076%, t=+3.74** vs
**thick-arbitrage group (SPY/QQQ/XLK/mega-cap) n=690, mean +0.053%, t=+1.37.**

Portfolio at $20k/signal: 474 signals, **+$150/day**, sd $592, worst day −$1,775,
**max drawdown −$2,774**, 41% losing days, Sharpe 3.87.

**Why I take it semi-seriously:** the thin-vs-thick split was **predicted by an earlier
12-symbol test and then confirmed on assets that test never saw** — it was not mined out of
the sweep it appears in. In a separate 216-test sweep (gold, silver, miners, oil, crypto,
leveraged ETFs, trend-following, swing momentum), **Benjamini-Hochberg FDR at 10% returned
ZERO discoveries** — so essentially everything else I tried failed.

---

## Strategy 2 — small-cap gap-and-go (Ross Cameron style), for context

Screen: gap ≥10% at the open, price $1–20, dollar volume ≥$10M, relative volume ≥5×.
Entry: break of the 5-minute opening-range high. Stop: opening-range low. Target: 2R.
Universe: entire US market **including delisted names** (survivorship-corrected).

1,008 triggered setups in Feb–Aug 2026: **+0.126R at 0.25% slippage, t=+3.04.** Break-even
slippage ≈0.6%. I then measured the **actual** quoted spread on those names at the entry
minute: **0.627% round trip median, p90 1.80%.** So the edge sits roughly at the real cost.

**Full-history check (the test that killed Strategy 1), ~70 setups sampled per year:**

| | | | | | |
|---|---|---|---|---|---|
| 2016 +0.204R | 2017 +0.132R | 2018 +0.268R | 2019 +0.234R | 2020 +0.097R | 2021 **−0.236R** |
| 2022 +0.126R | 2023 +0.258R | 2024 +0.270R | 2025 +0.041R | 2026 +0.131R | |

**ALL YEARS: n=774, mean +0.142R, t=+2.94. Positive in 10 of 11 years.**
Internal check: this sampling gives 2026 as +0.131R against +0.126R from the exhaustive
1,008-setup run, so the per-year sampling is unbiased.

**Its own weaknesses, which I want attacked:**
* **The early years are flattered.** I charge 2016 trades the spread I measured in 2026, and
  spreads have tightened a lot in a decade. 2016–2019 are both the strongest years and the
  most overstated. First half averages +0.187R, second half +0.098R — some of that "decay" is
  my own bias, but not obviously all of it.
* **Crowding.** Qualifying gappers went from **148 in 2016 to 1,748 in 2025** — twelve-fold —
  and 2025 is the weakest positive year (+0.041R). More setups, thinner edge.
* **The edge sits on top of its own cost.** Break-even slippage ~0.6% against a measured
  0.627% median real spread. It is a fill-quality question more than a signal question.
* Stop fills are modelled at the stop price; real stops on a reversing low-float runner slip
  worse, so the true break-even is BELOW the printed one. LULD halts are unmodelled.

Correlation between Strategy 1 and Strategy 2 daily P&L was +0.027 — now moot, since
Strategy 1 is dead.

---

## Weaknesses I already know about — please add to these

1. **RSI(2) is not new.** Larry Connors published it in the 2000s and its decay is widely
   documented. If it is public and profitable, why has it not been arbitraged away? A
   satisfying answer to that matters more to me than another backtest.
2. **~6 months of data.** 57–79 signals per asset. One regime. Nothing about Feb–Aug 2026
   guarantees anything.
3. **The thin/thick boundary is partly post-hoc.** Commodities I *labelled* thin-arbitrage
   (SLV, GDX, XLU, XLE) came out **negative**. I drew the line after seeing some results.
4. **Sharpe 3.87 (and 5.55 combined) is not credible.** Renaissance Medallion runs ~2.5–3 net.
   A number that high on public rules says my backtest is too kind somewhere. Where?
5. **Thresholds (10 / 90) are conventional but unswept.** They could simply be lucky.
6. **Overlapping windows** are not independent observations, so my t-stats are optimistic.
7. **Short side unmodelled:** no borrow cost, no hard-to-borrow constraint.
8. **Bond ETF spreads widen in stress** — 4bp is a calm-market assumption, and the strategy
   buys precisely when things are dislocating.
9. **Gap-and-go:** stop fills are modelled at the stop price, and real stops on a reversing
   low-float runner slip far worse. LULD halts are not modelled at all.
10. **Data plan:** backtests used SIP (full tape); live we only get IEX (~2% of volume). I
    re-ran the gap-and-go with signals from IEX and outcomes on SIP and it held (+0.246R,
    t=2.19), but I have not done that for RSI(2).

## Questions I would most like answered

- Is the thin-arbitrage story a real economic mechanism, or a story I fitted to noise?
- What is the published state of RSI(2) decay after ~2015?
- What would you need to see to believe or reject this?
- What is the most likely way these numbers are wrong that I have not listed?
