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
