# Gap-and-go: a strategy for independent review

> ## ⚠️ UPDATE, same day — THE EDGE IS EXACTLY ZERO AT REALISTIC FILLS
>
> After writing this I measured the quoted spread for **every individual setup** (1,344 of
> them) instead of applying one median, and charged each trade its own. Two findings, both
> fatal:
>
> **1. The edge lives ENTIRELY in the widest-spread names.**
>
> | | n | mean R | t |
> |---|---|---|---|
> | widest quintile only (spread 1.09%–16%) | 198 | **+0.332R** | **+3.49** |
> | **everything else (80% of setups)** | **790** | **+0.027R** | **+0.59** |
>
> **2. It survives only on a midpoint fill.** Slippage as a multiple of each setup's own
> measured spread:
>
> | assumption | mean R | t | $/day |
> |---|---|---|---|
> | 0.5× spread — fill at the midpoint | +0.088R | +2.13 | $205 |
> | **1.0× spread — cross the spread (what a marketable order does)** | **+0.001R** | **+0.01** | **$1** |
> | 1.5× spread — cross plus adverse move | −0.087R | −2.22 | −$204 |
>
> Filtering does not rescue it: capping spread at 2% gives −0.012R, because the edge was in
> the names being excluded.
>
> ⇒ **The strategy requires price improvement on low-float runners in the first minutes of
> the session.** A marketable order crosses the spread and nets nothing. Resting a limit at
> the mid invites adverse selection I cannot model without tick data. **Section 6's question
> about validating execution is now THE question, not a footnote.**
>
> This is the same shape as the opening-range-breakout strategy previously abandoned here:
> edge $3.85 per contract against friction of $4.00.

**Assume no prior context. Please try to break this, not confirm it.** I have listed the
weaknesses I already know at the end; the useful answer is the one I have not thought of.
Where you think I am wrong, say so plainly.

Everything below is **paper trading** (Alpaca, $100,000, simulated funds). No real money has
ever been at risk. I am trying to decide whether this is worth building into a live system.

---

## 1. The strategy, stated completely

A day-trade on small-cap stocks that gap up at the open on unusual volume — the setup retail
day traders call "gap and go". It is a **long-only, intraday, one-position-per-name** rule.

**Screen, at the open (9:30 ET):**

| filter | value | why |
|---|---|---|
| gap from prior close | ≥ +10% | something happened overnight |
| share price | $1–20 | the small-cap range where these run |
| dollar volume that day | ≥ $10,000,000 | tradable at all |
| relative volume vs 20-day median | ≥ 5× | "in play", not a quiet drift |

**Entry:** take the high and low of the **first 5 minutes**. Buy when price breaks the 5-minute
high.
**Stop:** the 5-minute low.
**Target:** entry + 2 × (entry − stop), i.e. a 2:1 reward-to-risk.
**Exit:** stop, target, or the close — whichever comes first. No overnight hold.

Roughly **8 qualifying setups per day** across the whole US market at present.

## 2. How it was tested

- **Universe: the entire US equity market**, ~11,000 tradable symbols — not a watchlist.
- **Including ~2,000 DELISTED symbols.** A small-cap backtest built only from names that still
  exist is biased upward by exactly the pump-and-dumps that later went to zero. Survivorship
  was measured, not assumed: delisted setups returned +0.119R against +0.126R for survivors —
  no material difference.
- **SIP (full consolidated tape)**, not IEX. IEX carries a few percent of volume and these
  names are nearly invisible in it.
- **Every trade charged real friction.** I measured the actual quoted bid-ask on those exact
  symbols at the exact entry minute — not an assumed constant.
- **When a single minute bar spans both stop and target, the STOP is assumed to hit first.**
  Minute bars cannot resolve the ordering and the conservative reading is the only honest one.

## 3. Results

**Exhaustive run, Feb–Aug 2026: 1,372 qualifying setups, 1,008 triggered.**

| slippage per side | n | win rate | mean R | t |
|---|---|---|---|---|
| 0.00% | 1008 | 44% | +0.205R | +4.89 |
| 0.25% | 1008 | 42% | +0.126R | **+3.04** |
| 0.50% | 1008 | 41% | +0.064R | +1.56 |
| 1.00% | 1008 | 38% | −0.053R | −1.33 |

**Break-even slippage ≈ 0.6% round trip.** A 41% win rate is what a 2:1 target produces, not
a defect.

**Full-history check, ~70 setups sampled per year, 2016–2026:**

| year | mean R | t | | year | mean R | t |
|---|---|---|---|---|---|---|
| 2016 | +0.204 | +1.32 | | 2022 | +0.126 | +0.80 |
| 2017 | +0.132 | +0.90 | | 2023 | +0.258 | +1.58 |
| 2018 | +0.268 | +1.79 | | 2024 | +0.270 | +1.64 |
| 2019 | +0.234 | +1.43 | | 2025 | +0.041 | +0.27 |
| 2020 | +0.097 | +0.59 | | 2026 | +0.131 | +0.79 |
| 2021 | **−0.236** | −1.44 | | | | |

**ALL YEARS: n=774, mean +0.142R, t=+2.94. Positive in 10 of 11 years.**

*Internal consistency check:* the per-year sampling puts 2026 at +0.131R against +0.126R from
the exhaustive 1,008-setup run. Different method, same answer.

**Expected P&L**, using the last two years (most like current conditions, ~7.9 setups/day,
+0.086R average): **+0.68R/day**, which on a $100,000 account is **~$194/day at $284 of risk
per trade** (2.3% of the book at risk across ~8 concurrent positions). On the last four years
it is ~$267/day. **43% of days lose money**; worst modelled day about −$2,300.

## 4. Context that should make you more suspicious, not less

I tested a **second** strategy alongside this one — RSI(2) mean reversion on bond and
international ETFs. Over Feb–Aug 2026 it looked **better than gap-and-go**: +0.231% per trade,
t=+4.40, backtest Sharpe 3.87.

**Over the full 2016–2026 record it lost money: n=10,381, mean −0.013%, t=−1.43, negative in
9 of 11 years.** 2026 was the best year in the decade and it was the year I had measured.

**Six months could not tell the two strategies apart.** That is why the eleven-year table
above exists, and it is the main reason I take gap-and-go semi-seriously. It is also why I
want you to look for the equivalent mistake that I have not yet caught here.

## 5. Weaknesses I already know — please add to these

1. **The early years are FLATTERED.** I charge 2016 trades the spread I measured in **2026**,
   and spreads have tightened a lot in a decade. 2016–2019 are the strongest years and the
   most overstated. First half averages +0.187R, second half +0.098R — I do not know how much
   of that apparent decay is real versus my own bias.
2. **Crowding.** Qualifying setups went from **148 in 2016 to 1,748 in 2025** — twelve-fold —
   and 2025 is the weakest positive year. More setups, thinner edge.
3. **The edge sits on top of its own cost.** Break-even ~0.6% against a measured **0.627%
   median** round-trip spread. But the distribution is what matters: **p10 = 0.26%, p90 =
   1.80%.** At ~0.9% per side the strategy loses money, so it may only be viable on the
   tight-spread subset — which I am testing now and have not yet answered.
4. **Stop fills are modelled AT the stop price.** Real stops on a reversing low-float runner
   slip far worse than entries do, so the true break-even is BELOW the printed one.
5. **LULD volatility halts are not modelled at all.** These names halt constantly, and a halt
   that reopens against the position is strictly worse than anything simulated.
6. **Only ~70 setups sampled per year** in the history table (minute bars for every setup
   across a decade exceeded my data plan). Per-year t-stats are therefore weak individually;
   only the pooled figure is meaningful.
7. **Paper fills will flatter this.** Paper trading fills instantly at the quote, which on a
   low-float runner is fiction. So paper results cannot validate the assumption the whole
   strategy rests on.
8. **My live data is worse than my backtest data.** The backtest used SIP; my subscription
   only gives real-time IEX (~2% of volume). I re-ran with signals from IEX and outcomes on
   SIP and it held (+0.246R, t=+2.19), but that is one check, not proof.
9. **This is a widely known retail setup**, popularised by Ross Cameron and taught in paid
   courses. If it is this well known, why does it still work?

## 6. What I would most like answered

- What is the most likely way these numbers are wrong that I have **not** listed?
- Is a 12× rise in qualifying setups with a falling edge evidence of crowding, or of a
  changed market structure that I am mis-measuring?
- How would you model stop slippage and halts honestly without access to tick data?
- Given weakness #7 — paper fills cannot test the binding assumption — what would you do to
  validate execution before committing real money?
- Is there a published literature on opening-range breakout decay I should read?
