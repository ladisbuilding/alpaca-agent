# The Committee

**An autonomous investment committee that trades defined-risk options on Alpaca — and knows
when not to.**

Eight AI agents argue about every trade. Deterministic code holds the veto. Every decision, and
every refusal, is on the public record.

**Live dashboard → [alpaca-agent.domfly.workers.dev](https://alpaca-agent.domfly.workers.dev)**

Built for the Alpaca × lablab.ai AI Trading Agents Hackathon, 28 Aug – 4 Sep 2026.
Paper trading only. Nothing here touches real money.

---

## The idea

Most trading agents are built to find trades. This one is built to be **honest about whether a
trade is worth taking** — because on measurement, most of the time, it isn't.

Three commitments follow from that, and they shape the whole system:

**1. Deterministic code holds the veto.** The LLM never picks a strike, never sizes past a cap,
and never places an order the risk gates did not approve. Alpaca's own reference architecture
states the rule this follows: *"Risk checks run as deterministic code, unit-tested, with no
model in the loop."* A number a model can talk itself into is not a number.

**2. Capability is enforced by infrastructure, not by prompts.** Each agent runs against its own
Alpaca MCP server, scoped by `ALPACA_TOOLSETS`. The advocates get 39 tools, **zero of which can
place an order**. The executor gets 41, six of which can. The Bear is not *told* not to trade —
it has no hands. A test asserts this against the running server.

**3. A refusal is a first-class result.** Most sittings end without a trade. The dashboard leads
with *why*, because "what it declined and on what grounds" is the more interesting half of an
autonomous trader's log.

## What it found

The agent was pointed at its own strategy and reported back that the edge wasn't there.

| Test | Result |
|---|---|
| Selling premium | IV/RV **1.05–1.22x** — implied is barely above realized. Not paid for the tail |
| Buying spreads at mid | Mid *is* fair value, so expected P&L = **minus friction** |
| Opening-range breakout, intraday | Real but thin: Sharpe **0.75** out-of-sample vs 1.58 in-sample |
| Opening-range breakout, held overnight | Hit rate **41–52%**, every t-stat inside noise. No edge |

The archived research this project inherited claimed a Sharpe of 3.31. That figure was the best
of a 288-combination parameter sweep and was never itself walk-forward validated — selection
bias. Re-run on six months of data that did not exist when those parameters were chosen, the
honest number is **0.75**, and the study's symbol rankings inverted.

So the committee's mandate is *deploy a small book and manage it well*, not *wait for a proven
edge*. **Low conviction is expressed through small size, not through refusal.** The transcripts
say so plainly when a trade is thin.

## Who is in the room

| Role | Scope | Job |
|---|---|---|
| **Premium scout** | 39 read-only tools | Nominates where premium is rich. Stands down when it isn't |
| **Directional scout** | 39 read-only tools | Nominates a directional lean with a checkable reason |
| **Bull** | 39 read-only tools | Argues for. Corrects its own side's evidence when it is wrong |
| **Bear** | 39 read-only tools | Argues to kill. Reserves KILL for genuinely bad, not merely unexciting |
| **Risk officer** | 39 read-only tools | Judgment the gates cannot encode — correlation, timing, today |
| **Portfolio manager** | 39 read-only tools | Picks the best available and sizes it |
| **Executor** | **41 tools, 6 can trade** | Places exactly what was approved. Never re-litigates |
| **Auditor** | 11 tools, none can trade | Reconciles fills. Deliberately hostile to good news |

**Scouts nominate a symbol and a stance — never a strike.** Deterministic code reads the live
chain and builds the structure. That is what keeps the strategy stateable and testable, which
the brief explicitly asks for.

## How a sitting runs

```
snapshot ─→ manage open positions ─→ scouts nominate ─→ deterministic build
   │                                                          │
   │                                                    PRE-GATE (cheap)
   │                                                          │
   └── one immutable snapshot ────────────── bull ⇄ bear ⇄ risk officer
       flows through the whole cycle                          │
                                                     FINAL GATE (binding)
                                                              │
                                                    executor ─→ decision record
```

Two ordering decisions are load-bearing:

- **Exits run first.** Freeing risk beats adding to the book, and a deterministic exit should
  never queue behind a debate.
- **Gates run before the debate.** A structure the rule layer already rejected is not worth $3
  of argument. A blocked sitting costs **$0.24**; one that reaches debate costs **$2.04**.

Everything is built and argued from **one immutable snapshot**. The first live Bear turn caught
its own inputs being stale and pointed out it was arguing about a trade that no longer existed.

## The gates

Fourteen deterministic checks, no model in the loop, [unit tested](agent/tests/test_gates.py)
with every blocking case paired against a baseline that passes once the condition is removed.

`KILL_SWITCH` · `STRATEGY_STOOD_DOWN` · `MARKET_CLOSED` · `NEAR_CLOSE` · `UNDEFINED_RISK` ·
`MISREPORTED_RISK` · `TRADE_TOO_LARGE` · `DAILY_LOSS_LIMIT` · `PORTFOLIO_RISK_CAP` ·
`TOO_MANY_POSITIONS` · `CONCENTRATION` · `DUPLICATE` · `WIDE_SPREAD` · `THIN_CREDIT` ·
`INSUFFICIENT_BUYING_POWER`

Two are worth calling out:

**`MISREPORTED_RISK`** independently re-derives a structure's max loss from the geometry of its
own legs. If a strategy claims less risk than its wings imply, it's blocked — because every
percentage cap downstream sizes off that number. It caught a bug in its own author's condor
builder within an hour of being written.

**`DUPLICATE`** keys on the *opportunity's lifecycle*, not a convenient clock. Same structure,
same strikes, same expiry is the same opportunity until that expiry passes. A five-minute window
is how a predecessor turned 15 decisions into 72 "trades".

Gates do not short-circuit — every violated rule is collected, so the record shows everything a
proposal broke rather than the first thing.

## Honest P&L

A previous system in this lineage reported **$2,015 at a 100% win rate**. Audited, it was **$89**.
Alpaca's own guidance says the same from the other side: *"Paper trading results do not predict
live performance."*

So the [audit layer](agent/src/committee/audit.py) makes three lies impossible to tell quietly:

1. **Order rows are not trades.** A four-leg condor is one decision. The headline always states
   decisions next to raw order rows.
2. **Our number must reconcile against the broker's.** Attribution comes from our decision log;
   the account's own equity change is the independent check. The gap is reported, never absorbed.
3. **A great number is a bug until proven otherwise.** Win rates ≥95% at n≥5, or returns above a
   defined-risk structure's own maximum, are anomalies rather than achievements.

The test suite reconstructs the original incident and asserts both tells fire.

**Nothing in this system may describe an order as a completed trade.** The first live run
reported "2 trades placed" while the broker showed zero fills — both were resting limit orders.
Only the Auditor, reading broker fill activity, gets to say a trade happened.

## Architecture

```
agent/       Python. Gates, chain, strategy, regime, 8 roles, MCP, cycle, audit, exits.
             Runs in a Cloudflare Container, woken by cron every 30 min during market hours.
api/         Hono on Cloudflare Workers + D1. Ingests cycle records; liveness watchdog.
www/         TanStack Start. The public dashboard.
container/   The runner Worker: cron trigger + Container binding.
```

Nothing depends on a laptop being awake. A watchdog emails if no sitting is recorded for 90
minutes during market hours — because the failure that kills an unattended agent is **silence**,
not an exception, and error reporting cannot see silence.

## Running it

```bash
cd agent
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cp ../.dev.vars.example ../.dev.vars     # Alpaca paper keys + Anthropic key

PYTHONPATH=src .venv/bin/python -m pytest tests/ -q        # 145 tests
.venv/bin/python scripts/discover_tools.py                 # prove the least-privilege scoping
.venv/bin/python scripts/smoke_chain.py QQQ                # live chain, no orders placed
.venv/bin/python scripts/run_cycle.py                      # a full sitting, dry run by default
.venv/bin/python scripts/run_audit.py                      # reconcile against the broker
```

`--live` places orders and is always explicit. Dry run is the default, because the failure mode
of getting that backwards is placing orders you did not intend to audit.

## Controls

| | |
|---|---|
| `DRY_RUN` | Deliberate and record, place nothing |
| `STRATEGY_MODES` | Per-family: `income:exit_only,directional:active`. **Exit-only stands down entries while still managing what it holds** — a position you have stopped managing is more dangerous than one you never opened |
| `KILL_SWITCH` | Global. Blocks new positions and flattens existing ones |
| `DAILY_USD_CAP` / `MAX_CYCLE_USD` | Soft spend ceilings, reported on every cycle |

## Prior art

[TradingAgents](https://github.com/TauricResearch/TradingAgents) established the multi-agent
bull/bear pattern this builds on. [IgorGanapolsky/trading](https://github.com/IgorGanapolsky/trading)
converged independently on deterministic gates and paper-first discipline — its
*"guardrails first, edge second"* is this project's thesis stated better, and its
per-strategy exit-only switch is borrowed here directly.

What is different: this is **options-native**, runs entirely through **Alpaca's MCP server**
with per-role capability scoping, holds the veto in **deterministic code**, and **audits its own
P&L against the broker** rather than reporting its own order log.

## Disclosure

Paper trading only, on simulated funds. Not financial advice. Options involve risk, and an
autonomous agent trading them involves more. The measurements in this README are honest
reporting of what was found, including where the strategy failed — that is the point.
