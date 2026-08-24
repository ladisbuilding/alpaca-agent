# CLAUDE.md — alpaca-agent

## What this is
An entry for the **Alpaca × lablab.ai AI Trading Agents Hackathon**, 28 Aug – 4 Sep 2026.
Autonomous AI trading agent on **Alpaca's Trading API + MCP server/CLI**, paper account seeded
$100,000, **options trading mandatory**. Prize pool $6,000 (site figure; the email said $5,000).

Full evaluation → `~/brain/wiki/concepts/ideas.md` (2026-08-24 entry).

## ⚠️ Why Luke is doing this — get the goal right
**Not to win the P&L prize.** His stated reason: *"I think it would be fun and maybe I will get some
professional benefit from it."*

That matters, because **a ~6-trading-day P&L contest with mandatory options is a VARIANCE contest, not
a skill contest.** You'd be optimising *P(top-3 of N)*, which is maximised by concentrated, leveraged,
unhedged bets — so **good risk management actively lowers your odds of winning**. The format even
contradicts itself: it requires documenting "risk gates" while scoring rewards discarding them.

**So optimise for the two things that actually pay out here:**
1. **Durable skill** — Alpaca's MCP server is a genuinely interesting primitive (a programmable
   brokerage: plug in a key, place orders on US stocks/options/ETFs/crypto, they hold the regulated
   parts). That knowledge outlives the hackathon.
2. **The 2 Social Engagement Awards** — a *separate, lower-variance* judging track on creativity and
   engagement, not luck. ⚠️ This is build-in-public, Luke's documented drain — so if it's pursued,
   automate the posting rather than grinding it manually.

**Corollary: build the agent you'd actually be proud of** (real risk gates, Kelly-aware sizing,
explainable decisions) and accept it will probably lose the P&L race to someone who YOLO'd. That is
the correct trade given the stated goal.

## ⭐⭐⭐ READ THIS FIRST — you are RESUMING, not starting

Luke did six months of trading work in 2026 that is **already on this machine**. Do not rebuild it.
Full write-up: `~/brain/wiki/discoveries/prior-trading-work.md`

**A validated strategy already exists, backtested on Alpaca's own historical API:**
- **QQQ Opening Range Breakout**, optimised params (R30 RR1.0 V1.0 T12, EMA filter OFF):
  **Sharpe 3.31 · +$4,523 over 6 months on $25k · PF 1.58 · 50.7% win · max DD −4.9%** · stable in
  walk-forward. Source: `~/brain/archived-projects/stock-trader/research/backtest-results.md`
- **TSLA ORB** — secondary, profitable, fewer trades, less confidence.
- **VWAP mean reversion → no edge.** **SPY ORB → no edge** (confirmed in both test periods). Don't retest.
- Its written next step was literally *"Paper trade QQQ ORB and TSLA ORB on Alpaca to validate
  real-time execution"* — **never done. That is this hackathon.**

⭐ **The blocker that stopped it is gone here.** The backtest flagged **PDT** (5.6 trades/week vs the
3/week limit under $25k). The competition account is **$100,000**, so PDT does not apply.

**Options research already exists** (and options are MANDATORY here):
`~/brain/archived-projects/stock-trader/research/spx-iron-condor-butterfly-research.md` —
SPX **iron condors** (4-leg defined-risk, profits in a range, **~60–68% historical win**) vs
**iron butterflies** (ATM shorts, larger credit, much narrower profit zone, **~40–50%**).

**Dead ends already paid for — do NOT re-run:**
- Triangular crypto arb + Alpaca (explicitly logged as a dead end).
- Crypto arb is **fee-negative**: $0.43 gross vs $1.74 fees on 3 trades.

**Other code to mine rather than rewrite:** `~/brain/archived-projects/trade-boy` (AI trader +
sentiment: `src/server/trading/ai-trader.ts`, `SENTIMENT.md`, news ingestion) and
`~/brain/archived-projects/trade-bot` (live execution engine, WebSocket price feeds, position merging).

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
