# CLAUDE.md — alpaca-agent

## What this is
An **autonomous options trading agent** on **Alpaca's Trading API + MCP server**, running a
committee of LLM roles behind deterministic risk gates. **Paper account, $100,000.**

Built originally for the Alpaca × lablab.ai hackathon (28 Aug – 4 Sep 2026); **Luke withdrew
from the contest on 2026-08-31 — see the ruling below.** It now exists to be made genuinely
good rather than to be submitted. Origin evaluation → `~/brain/wiki/concepts/ideas.md`
(2026-08-24 entry).

## ⚠️⚠️ THE CONTEST IS OFF — Luke's ruling, 2026-08-31

**Luke decided NOT to enter the hackathon.** The goal is now, in his words:
*"I just want to perfect a trading system."*

**This is a better brief, and the old one was fighting itself.** The note this replaces argued
that a ~6-trading-day P&L contest with mandatory options is a **variance contest, not a skill
contest** — you'd be optimising *P(top-3 of N)*, which is maximised by concentrated, leveraged,
unhedged bets, so **good risk management actively lowered the odds of winning.** The format
demanded documented risk gates while scoring rewarded discarding them. That tension is gone.

**What this changes:**
- **No deadline.** Nothing needs to ship by a date. Measure properly instead.
- **Dead:** dedicated competition account, submission write-up, video, cover image, social
  posting, the two Social Engagement Awards. `docs/LAUNCH.md` is now history, not a runbook.
- **Alive and now the whole point:** real measured edge, honest accounting, risk gates that
  mean something. `www` and `/deck` stay — they are how you READ the system.
- **Stays paper.** `paper-api.alpaca.markets`, `paper=True` hardcoded, no live key ever in
  this repo. `DRY_RUN=false` means "really place orders ON PAPER", nothing more.

⭐ **The standard is no longer "would this impress a judge in six days" but "would I trust
this with money".** Those pull in opposite directions, which is exactly why the switch helps.

## 📊 What the record actually says (as of 2026-08-31, dev account PA35CQR61R2Q)

Equity $99,537 · **all-time −$462** · 12 legs open. Broken down by sleeve, which is the only
breakdown that matters:

| sleeve | P&L |
|---|---|
| **INCOME** (sell premium where the breach rate says it is rich) | **+$32 open, and every closed structure green: +$21, +$12, plus an IWM condor expiring at max profit** |
| **DIRECTIONAL** (buy debit spreads on a narrative) | **−$509. 0-for-4.** |

⇒ **Every dollar lost is the directional sleeve.** The income sleeve works. This is the single
most important fact about the system and it should drive what happens next.

⚠️ The directional nominations were narrative ("QQQ fell 6 of 7 sessions"), not catalyst. The
one catalyst-sourced trade (NVDA post-earnings) was the only directional position that ever
behaved. The screener already computes catalysts — the committee only FLAGS them. Requiring a
catalyst is a small, evidenced change.

## 🔬 The only signal with a measured edge that clears its costs

**Ross Cameron gap-and-go** (`agent/scripts/test_gap_and_go.py`): market-wide, out-of-sample,
**survivorship-free** (delisted names included), 1,008 triggered setups —
**+0.126R at 0.25% slippage, t=+3.04.** Break-even slippage ≈0.6%.
Compare **ORB** (edge $3.85 = friction $4.00, dead) and **RSI(2)** (pooled t=1.79, ambiguous).

Blocked on architecture, not on evidence: a `Nomination` carries
`(underlying, sleeve, direction, conviction)` and **cannot carry entry/stop levels**;
`verify_defined_risk()` derives max loss from **leg geometry** and has no path for shares;
the cron is **30-minute** against a setup needing the 9:30–9:35 range. With the deadline gone,
this is now buildable properly.

## ⭐⭐⭐ READ THIS FIRST — this is a FRESH BUILD (Luke's ruling, 2026-08-24)

**Do NOT port, copy, or adapt any old code.** Luke was explicit: *"i dont want to use any old code —
this is a new project… we are starting fresh."* Every line here is written new.

**The old work is REFERENCE ONLY — read it for findings, never for source.** Six months of trading
work from 2026 sits in `~/brain/archived-projects/{stock-trader,trade-bot,trade-boy}`; write-up at
`~/brain/wiki/discoveries/prior-trading-work.md`. Mine it for *what was learned* (which strategies
had edge, which were dead ends, how paper P&L lied) — that saves real time. Do not mine it for files.

**A validated strategy already exists, backtested on Alpaca's own historical API:**
- **QQQ Opening Range Breakout**, optimised params (R30 RR1.0 V1.0 T12, EMA filter OFF):
  **Sharpe 3.31 · +$4,523 over 6 months on $25k · PF 1.58 · 50.7% win · max DD −4.9%** — but read the
  ⚠️ below before trusting that number. Source: `~/brain/archived-projects/stock-trader/research/backtest-results.md`
- **TSLA ORB** — secondary, profitable, fewer trades, less confidence.
- **VWAP mean reversion → no edge.** **SPY ORB → no edge** (confirmed in both test periods). Don't retest.
- Its written next step was literally *"Paper trade QQQ ORB and TSLA ORB on Alpaca to validate
  real-time execution"* — **never done. That is this hackathon.**
- ⚠️ **The Sharpe 3.31 is best-of-288, not an out-of-sample result.** Verified 2026-08-24 against
  `research/backtest-results.md`: the **walk-forward passed on the BASELINE params** (Sharpe 1.78
  in-sample → 1.93 out-of-sample). The 3.31 came from a **288-combination parameter sweep run
  afterwards that was never itself walk-forward validated** — that is selection bias. **Expect
  Sharpe ≈1.9, not 3.3.** Same failure family as the $2,015→$89 audit below: trust the
  out-of-sample number, never the best-of-N number.
- ⚠️ **The old options research is on the wrong broker.** The prior iron-condor work targeted
  **tastytrade**, and the old Alpaca client had **no options support whatsoever**. Options are
  **mandatory** here ⇒ **Alpaca options (chain, delta-based strike selection, multi-leg orders) is
  genuinely new work with no prior art to lean on.**

⭐ **The blocker that stopped it is gone here.** The backtest flagged **PDT** (5.6 trades/week vs the
3/week limit under $25k). The competition account is **$100,000**, so PDT does not apply.

**Options research exists as READING** (and options are MANDATORY here) — note it targets tastytrade,
so the *findings* transfer but none of the code does:
`~/brain/archived-projects/stock-trader/research/spx-iron-condor-butterfly-research.md` —
SPX **iron condors** (4-leg defined-risk, profits in a range, **~60–68% historical win**) vs
**iron butterflies** (ATM shorts, larger credit, much narrower profit zone, **~40–50%**).

**Dead ends already paid for — do NOT re-run:**
- Triangular crypto arb + Alpaca (explicitly logged as a dead end).
- Crypto arb is **fee-negative**: $0.43 gross vs $1.74 fees on 3 trades.

**Other prior work worth READING (not copying — see the fresh-build ruling above):**
`~/brain/archived-projects/trade-boy` (AI trader + sentiment: `SENTIMENT.md`, news ingestion) and
`~/brain/archived-projects/trade-bot` (live execution engine, WebSocket feeds, position merging, and
`tasks/lessons.md` — the source of the paper-P&L warning below).

## ⚠️⚠️ PAPER P&L LIES — Luke has already been burned by exactly this
From `~/brain/archived-projects/trade-bot/tasks/lessons.md`:
> Paper trading showed **"$2,015 P&L, 100% win rate."** After audit: **$89.**

Cause: a **5-minute dedup window** re-traded the same opportunity every ~6 minutes, so **72 "trades"
were 15 real decisions** — ~100× inflation. Also: *instant-close paper trades show theoretical, not
achievable, profit.*

**Therefore, non-negotiable in this project:**
- **Dedup window must match the opportunity's lifecycle**, not a convenient default.
- **Audit individual fills before believing any total.** Never report an aggregate you haven't
  inspected trade-by-trade for duplicates and false positives.
- **Break P&L down by strategy**, never a single headline number.
- This contest is *judged* on paper P&L — a number that is 23× too good is not a win, it's a bug.

## ⏱️ Scope discipline
**Capped spike, not a week.** In flight right now: Celita in App Store review, Careside submission,
Towers of Light apps in review, Consensia client blockers, chaz waiting on Chad. This is also against
the standing [[Lad 90-Day Growth Plan]] "no new apps" ruling — which is fine as a deliberate,
time-boxed exception, not as a drift.

## Rules
- **Paper trading only.** Simulated funds, real market data. Nothing here touches real money — and
  nothing in this repo should ever hold a live-trading key.
- **A dedicated hackathon paper account is REQUIRED.** A reused/existing account is disqualified.
  The account ID must be in the submission so judges can read the P&L.
- Starting balance must be set to **$100,000**.
- Submission needs a **one-page write-up**: AI logic, risk gates, Alpaca infrastructure.
- **Options must be part of the strategy.**
- Never commit API keys — `.dev.vars`, gitignored, like the rest of the fleet.
- ⚠️ Winners must supply documentation within 90 days or forfeit; Alpaca may use name/likeness/project
  for publicity. Submissions must be original and MIT-compliant.

## Dev Log
`DEVLOG.md` — append a dated entry after meaningful work.
