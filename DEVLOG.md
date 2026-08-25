# alpaca-agent — Dev Log

## Current State

**Phase:** dev environment LIVE and verified. ⭐ **FRESH BUILD — do not port old code** (Luke's ruling
2026-08-24); `archived-projects/` is reading material only. See CLAUDE.md.
**Event:** Alpaca × lablab.ai AI Trading Agents Hackathon, 28 Aug – 4 Sep 2026. Kickoff **Fri 28 Aug,
8:00 AM PDT**. Submissions close **Thu 4 Sep, 8:00 AM PDT**.
**Goal (Luke's words):** *"fun and maybe some professional benefit"* — but see the judging-criteria
correction below: this is **not** the pure P&L lottery the plan originally assumed.

**Dev account (NOT the submission account):** `alpaca-agent DEV` · **PA35CQR61R2Q** · $100,000 cash ·
$400,000 buying power · `options_trading_level: 3` (top tier — multi-leg spreads allowed, no
application). Keys in gitignored `.dev.vars`, verified against the live API.
⚠️ **Alpaca caps the account at 3 paper accounts total.** 1 old (`PA3CAO6AR0OV`, $89.5k) + this DEV
one = **2 used, exactly 1 slot left.** That last slot is RESERVED for the brand-new dedicated
submission account created on **launch day**. Do not spend it.

**Verified working (2026-08-24):** account · options contracts · options snapshots **with greeks +
IV on the FREE `indicative` feed** · stock bars. Delta-targeted strike selection proven live
(QQQ 16-delta condor body: 696P / 716C, real bids).

**Next:** (1) decide strategy shape — options are mandatory and P&L is only 1 of 5 judging criteria;
(2) build the agent (autonomous, on Trading API, using **MCP server OR CLI** — either satisfies the
rule); (3) budget a full day for the submission package (video + slides + cover image + public repo +
**hosted demo URL**); (4) launch day: fresh dedicated account at $100k.

---

## Log

### 2026-08-24 — project created
- Evaluated the hackathon before committing to it (→ [[Ideas]] 2026-08-24). Key finding recorded in
  CLAUDE.md: **the P&L track is a variance lottery**, so the build targets durable skill (Alpaca's MCP
  server) and the separate engagement award instead.
- Scope deliberately capped — several store submissions and a client project are mid-flight.
- ✅ **Luke enrolled on lablab.ai** (2026-08-24). **2,056 approved participants** and climbing.
- ⭐⭐ **Pre-building is explicitly ALLOWED**, which changes the plan: *"Use any paper account to start
  building… explore the API, MCP server, and CLI, prototype your agent, and test strategies. Use any
  paper account you like during development."* Only the **final submission** needs a brand-new dedicated
  account at $100,000 (a reused account is disqualified, and its ID goes in the submission).
  ⇒ **The 4 days before kickoff are development time.**
- ⭐ **Engagement track has a concrete, small spec:** *"up to **5 links** to posts on **X or LinkedIn**
  during the hackathon… tagging both lablab.ai and Alpaca."* 5 posts / 7 days = the whole ask for the
  track with far better odds than P&L. Feed it from DEVLOG → the lad `/admin` post-ideas pipeline
  (deployed + runtime-verified 2026-08-24).
- **Signup:** `https://alpaca.markets` (the hackathon's "Create paper account" button is just that, plus
  utm tracking). Docs: `https://docs.alpaca.markets/us/docs/getting-started`.
- **Official resources worth reading before kickoff:**
  `github.com/alpacahq/alpaca-skills` (skills for AI-powered trading) · `github.com/alpacahq/cli` ·
  `github.com/alpacahq/alpaca-py` · `github.com/alpacahq/alpaca-trade-api-js` ·
  `docs.alpaca.markets/us/docs/getting-started-with-trading-api`
- **Registration link:** `https://lablab.ai/ai-hackathons/alpaca-ai-trading-agents-hackathon?enroll=true`
  ✅ **No entry fee** — nothing on the page charges to enter, and Alpaca paper trading is explicitly
  "free, no card required". Luke is already logged into lablab.ai. He is signing up himself (creating
  or authorising accounts is not something I do on his behalf).
- ⚠️ **Money only appears on the WINNING side, and it has strings:** W-9 (US) / W-8BEN (non-US),
  government photo ID and bank details required **before** payment; **US winners over $600 get a
  1099-MISC** (1st = $2,500 and 2nd = $1,500 both clear that); non-US payments face 30% US withholding
  absent a treaty claim; gross prizes reduced by withholding and wire fees; documentation due within
  **90 days** or the prize is forfeited.
- ⏰ **Starts Friday 28 Aug 2026, 8:00 AM Pacific.**

### 2026-08-24 (later) — dev account live, options path proven, two founding premises corrected
- ⭐ **Luke's ruling: FRESH BUILD.** *"i dont want to use any old code — this is a new project."* The
  six months of archived trading work is **reference only** — mine it for findings, never for source.
  CLAUDE.md rewritten accordingly.
- ✅ **Created `alpaca-agent DEV` paper account** via the dashboard: **PA35CQR61R2Q**, $100,000,
  $400k buying power, sync-to-live left OFF. Generated paper keys → gitignored `.dev.vars` (chmod 600).
- ✅ **Auth + data verified live**, not assumed: `/v2/account` returns ACTIVE/$100k, and
  **`options_trading_level: 3`** — Alpaca's top tier, so **multi-leg spreads (iron condors) need no
  application.**
- ⭐⭐ **Greeks are FREE.** `v1beta1/options/snapshots/{sym}?feed=indicative` returns `greeks` +
  `impliedVolatility`. **Gotcha that nearly cost the strategy:** the first 2-contract sample came back
  with **no greeks**, which reads exactly like "greeks are a paid feature." They were deep-ITM
  contracts, which omit them. Widening to `limit=1000` gave **282 contracts with greeks**.
  ⚠️ **A field missing from a small sample is not an absent capability — widen the sample first.**
- **`feed=opra` → HTTP 403 `"OPRA agreement is not signed"`** — an *agreement*, not a paywall, and
  irrelevant while indicative carries greeks. (Note: the Social Engagement prize includes 1 month of
  Algo Trader Plus, which is the OPRA tier.)
- ✅ **Delta-targeted strike selection proven end-to-end** on the free feed — QQQ ~16-delta short
  strikes 696P (Δ−0.164, bid 0.98) / 716C (Δ+0.154, bid 0.66), IV 0.22/0.16.
- ⚠️⚠️ **RULES READ FROM SOURCE — two founding premises were wrong:**
  1. **P&L is one of FIVE judging criteria** (P&L · Technology Implementation · Creativity &
     Originality · Presentation & Execution · Social engagement). The "6-day P&L contest is a variance
     lottery, EV ≈ $7, good risk management lowers your odds" framing **does not hold for the main
     prizes.** Craft and presentation are scored directly.
  2. **The submission is far bigger than "a one-page write-up":** title, short + long description,
     tags, **cover image, video presentation, slide presentation, public GitHub repo, demo platform +
     application URL**, account ID, and up to 5 social links. **Budget a day for this.**
  3. Core requirement is **"MCP *or* CLI"** — MCP is not mandatory.
  4. **No account-naming rule exists.** Judges identify the account by **ID**.
  5. Teams 1–6. Enrolment now **2,080**.
- ⚠️ **3-paper-account cap discovered.** 2 of 3 used; the last slot is reserved for launch day.

### 2026-08-24 (later still) — strategy layer built and verified on the live chain
- **`agent/src/committee/chain.py`** — OCC symbol parsing, Alpaca snapshot parsing, liquidity
  filtering, delta-based strike selection, wing selection. Contracts arriving **without greeks**
  (deep ITM) survive parsing with `delta=None` rather than being dropped, so callers can see how
  much of a chain is genuinely usable.
- **`agent/src/committee/strategy.py`** — iron condor, credit verticals (put = bullish, call =
  bearish), debit verticals (the directional sleeve). ⭐ **Default fill assumption is CONSERVATIVE**
  (sell at bid, buy at ask). A structure that only clears its thresholds at mid will not clear them
  live — and paper fills already flatter you.
- ⭐ **Found and fixed a real correctness bug in my own gate:** `verify_defined_risk` summed wing
  widths across puts AND calls, overstating an iron condor's max loss ~2x. Non-overlapping shorts
  can only finish ITM on one side ⇒ max loss is the **widest side**, not the sum. Inverted/"guts"
  structures still sum (they genuinely can lose both sides). Would have mis-sized every downstream
  percentage cap.
- **Debit structures are now verified too.** `verify_defined_risk` returns None for them (the short
  sits further OTM than the long, so there is no protective leg to measure), which left them
  entirely unchecked. A debit vertical's max loss IS the debit — now asserted.
- ✅ **59 tests passing.** ✅ **Live smoke (`agent/scripts/smoke_chain.py`) builds all 5 structures
  from the real QQQ chain** on `PA35CQR61R2Q`: 1000 contracts parsed, ~285 with greeks, ~233 pass
  liquidity; 16-delta targets resolve to **put 699 (Δ−0.148) / call 713 (Δ+0.136)** with real bids.
  Smoke now queries **Alpaca's `/v2/clock`** instead of assuming market hours (half-days, holidays).
- ⚠️⚠️ **OPEN QUESTION for Tuesday — the thresholds are untested in daylight.** On after-hours
  quotes the gates block nearly everything: `WIDE_SPREAD` at 16.8% (limit 15%) and `THIN_CREDIT` at
  7.3% (floor 10%). That is *probably* an after-hours artifact — spreads widen and quotes go stale
  once the book empties — but it might mean `max_bid_ask_pct` / `min_credit_to_max_loss` are simply
  too strict. **Do not tune them off closed-market data.** Re-run the smoke during Tuesday's session
  and set them from what a live book actually offers. A gate that blocks 100% of trades is as broken
  as one that blocks none.

### 2026-08-24 (cont.) — MCP wired; least-privilege PROVEN, not asserted
- Installed `alpaca-mcp-server` **2.3.0** into `agent/.venv` (pip works; `uv` not required).
  Entry point `alpaca-mcp-server`; supports `--transport stdio|streamable-http|sse`.
  ⭐ **`streamable-http` matters** — the server can be hosted and reached over HTTP, which is what
  makes the Cloudflare Container plan work (and would also suit Anthropic's MCP URL connector).
- **`agent/scripts/discover_tools.py`** connects over stdio and enumerates the REAL v2 tool surface.
  v2 renamed everything, so role definitions are built from what the server reports, never from docs.
- ⭐⭐ **Least-privilege verified end to end:**
  - research scope (`stock-data,options-data,news,assets,account`) → **39 tools**
  - executor scope (`trading,options-data,assets,account`) → **41 tools**
  - unrestricted → **72 tools**
  - order-placing tools visible to the **executor**: `place_option_order`, `place_stock_order`,
    `place_crypto_order`, `cancel_order_by_id`, `cancel_all_orders`, `replace_order_by_id`
  - order-placing tools visible to **research roles: NONE**
  ⇒ **The Bull/Bear/Scouts/Risk Officer cannot place a trade — the tool is absent from their
  context.** The script asserts this and fails loudly if it ever stops holding.
- ⭐ **`place_option_order` accepts single-leg AND multi-leg** ⇒ iron condors go through MCP directly,
  no REST fallback needed.

### 2026-08-24 (cont.) — committee roles + scoped MCP sessions
- **`agent/src/committee/mcp_client.py`** — `scoped_session(toolsets, creds)` starts an MCP server
  limited to one role's toolsets and yields a session plus Anthropic-shaped tool schemas.
  `ScopedSession.call()` raises `PermissionError` for out-of-scope tools (the server would reject
  it anyway; this just fails earlier and more legibly).
- **`agent/src/committee/roles.py`** — 8 roles on `claude-opus-5`, effort tuned per role
  (scouts medium, advocates high, risk officer xhigh, executor low).
- ⭐⭐ **The division of labour is what keeps the strategy "clear, testable":**
  **Scouts nominate (underlying, sleeve) with a rationale — they never choose strikes.**
  Deterministic code builds the structure from the live chain. Bull/Bear argue about the built
  structure. Risk Officer advises; `gates.evaluate()` vetoes. PM sizes within caps. Executor places.
  ⇒ **An LLM never picks a strike, never sizes past a cap, and never places an order the
  deterministic gates did not approve.**
- ⭐ **Caught a hole in my own invariant while writing it.** The Auditor was given `trading` so it
  could read orders — but that scope also *places* them, silently breaking the one-role-can-trade
  claim. Probed the server: **`account` alone exposes `get_account_activities`,
  `get_account_activities_by_type`, `get_portfolio_history` and ZERO order-placing tools.**
  Auditor now runs on `account`. It is also the better audit source — **orders record intent,
  fills record what happened.**
- **Invariant asserted at import time:** `roles.py` fails on import if any role other than
  `executor` holds `trading`. A careless toolset edit breaks the build, not a trading morning.

### 2026-08-24 (cont.) — LLM layer live; the debate is REAL, and it has a price
- **`agent/src/committee/llm.py`** — `run_turn()` runs one role against its scoped MCP tools:
  `claude-opus-5`, adaptive thinking, per-role `effort`, server-side refusal fallback
  (`server-side-fallback-2026-07-01`) so one tripped classifier cannot halt a trading session.
  All tool results return in a SINGLE user message (splitting them teaches the model to stop
  calling tools in parallel). Every turn records its full tool-call trail as **evidence**.
- ⭐⭐ **First live Bear turn — the concept is validated.** Given a QQQ condor to attack it called
  6 tools unprompted and returned a substantive KILL: caught that the supplied deltas were stale
  (live 699P −0.2315 vs the −0.148 in the prompt), compared implied vs realized 2-day vol
  (11 of 26 recent windows breached the wings), found **NVDA reporting on expiry day**, showed the
  credit did not reconcile with live mids, priced the round-trip exit at 13–27% of credit — then
  **conceded the one point it could not attack**: *"Book is empty, so no correlation objection."*
  ⇒ **The debate produces information, not theatre.** This was the project's biggest open risk.
- ⚠️⚠️ **COST IS A REAL CONSTRAINT.** That single turn: **131,836 input / 7,806 output tokens ≈ $0.86**.
  Input is dominated by option-chain tool dumps. Extrapolated: ~$5/cycle × 6 roles, every 30 min
  over a 6.5h session ≈ **$65/day, ~$400 for the week.** Mitigations before it runs unattended:
  (1) **prompt caching** on system prompts + tool definitions, (2) **trim chain payloads** before
  they reach the model — the deterministic layer already has the parsed chain, the LLM does not
  need the raw dump, (3) lower scout effort, (4) fewer cycles/day.
- **Note:** Alpaca's MCP wraps every tool result in `_alpaca_mcp_security` with
  `trust: "untrusted_tool_output"` — a built-in prompt-injection guard. Good; keep it intact.
- Anthropic key currently reused from `chaz`. **Luke is issuing a dedicated key** so hackathon
  spend is tracked separately.

### 2026-08-24 (cont.) — FULL CYCLE RUNS END TO END
- **`agent/src/committee/market.py`** — `MarketSnapshot`, immutable, taken once per cycle. Every role
  argues from the SAME snapshot (the stale-delta lesson). Fetched over REST, not MCP: MCP returns
  text shaped for a model, the deterministic layer wants parsed JSON. The agents use MCP throughout,
  which is where the hackathon requirement lives.
  ⭐ **Broker legs are collapsed into committee positions** — a 4-leg condor is ONE position, not 4.
  Counting legs would blow `max_concurrent_positions` after two trades, the same error family as the
  15-decisions-became-72-trades bug.
- **`agent/src/committee/cycle.py`** — the orchestration. Two load-bearing ordering decisions:
  1. ⭐⭐ **Gates run BEFORE the debate.** A structure the deterministic layer already rejected is not
     worth $3 of argument. The record still shows exactly why it was refused.
  2. ⭐ **One snapshot through the whole cycle.**
- **Model tiering (Luke's call): Opus 5 where a judge reads the output** (bull, bear, risk officer,
  PM, auditor), **Sonnet 5 where nobody does** (scouts, executor). ⚠️ **Sonnet not Haiku** —
  a scout that misses a nomination costs a trade that never gets debated, and a weak nomination
  poisons a good debate. Screening is cheap to run and expensive to get wrong.
- ⭐⭐ **PROMPT CACHING WORKS — cost collapsed.** Breakpoints on the last tool definition and the
  system block. First full cycle: **$0.24**, with **9,699 fresh input tokens vs 41,430 cache reads
  (~81% hit rate)** — against $0.86 for a single uncached turn earlier. Week estimate now well under
  $50 rather than ~$400.
- ⚠️ **`fallbacks` is NOT universal.** Sonnet 5 returns `400 "'claude-sonnet-5' does not support the
  fallbacks parameter"`. It is Opus-5 / Fable-5 only, and is now sent only to models that accept it.
- ⚠️ **One role failing must not end the cycle.** A 400 in a scout killed the entire run via an
  asyncio TaskGroup. `run_turn` now catches per-turn, records the error on the Turn, and returns;
  scouts catch session-start failures too. A transient 429 during a session should cost one opinion,
  not the session. **Essential for a 6-day unattended run.**
- **`agent/scripts/run_cycle.py`** — dry run by DEFAULT, `--live` explicit. Writes one JSON record per
  cycle to `runs/`, which becomes the api's source of truth and the dashboard feed.
  ⭐ **Dedup fingerprints are read back from prior run records on disk**, so a restarted container
  does not forget what it already traded and re-enter the same structure.

### 2026-08-24 (cont.) — api + dashboard DEPLOYED
- ✅ **`api/` — Hono on Cloudflare Workers + D1. LIVE: `https://alpaca-agent-api.domfly.workers.dev`**
  `POST /cycles` ingests a cycle record; `GET /cycles`, `/cycles/:id`, `/latest`, `/summary`,
  `/refusals` serve it. Public read (judges click without a login), shared-secret write.
  **D1 (`alpaca-agent`, id 8ac0e776-…) not fleet Postgres** — a deployed Worker could not reach fleet
  Postgres in Aug, exactly the failure that would bite mid-competition. Records stored as JSON with
  columns only for what we filter/aggregate, so a new committee role needs no migration.
  ⭐ **`/summary` reports `distinct_structures_traded` NEXT TO `executed_decision_rows`.** They should
  match; divergence means the same structure was entered twice and the dedup gate has a hole.
  Surfaced rather than averaged away — the direct answer to $2,015→$89.
- ✅ **`www/` — TanStack Start on Workers. LIVE: `https://alpaca-agent.domfly.workers.dev`**
  **This is the hackathon's required Application URL.**
- ⭐⭐ **Design: three typographic voices, one per speaker** — Bodoni Moda masthead (engraved
  certificate / institutional finance), Source Serif for the agents' prose (argument is
  human-shaped), IBM Plex Mono for the deterministic layer (gate names, strikes, verdicts).
  **The typography encodes who is talking.** Refusals render as a rotated mono stamp across a paper
  document panel — code visibly overriding rhetoric. Deliberately NOT a KPI-row dashboard.
- ⚠️⚠️ **Worker-to-Worker fetch on workers.dev LOOPS BACK AND 404s.** SSR loader fetching
  `alpaca-agent-api.domfly.workers.dev` from the www Worker returned **404** while the same URL
  returned 200 from curl. **Fix: a service binding** (`services: [{binding: "API", service:
  "alpaca-agent-api"}]`) + a `/api/*` proxy in `src/worker.ts`. Also removes the public hop and makes
  everything same-origin, so CORS stops applying. → [[reference_worker_to_worker_fetch_needs_service_binding]]
- ⚠️ **A silent catch turned a broken fetch into an empty state.** `fetchJson` swallowed the 404 and
  the page said *"No sittings on record yet"* — reading as "the agent has done nothing" rather than
  "the dashboard is broken". It now returns the error and the page distinguishes the two.
  A 404 on `/latest` before the first sitting is still a legitimate empty state; only a `/summary`
  failure means the record is genuinely unreachable.
- Data loads client-side and refreshes every 60s — a relative URL cannot resolve during SSR, and a
  dashboard watched during market hours wants to refresh itself.
- ⚠️ `@cloudflare/workers-types` must be **^5.x** with wrangler 4.125 (v4 fails ERESOLVE).

### 2026-08-24 (cont.) — liveness watchdog + private repo
- ✅ **Repo: `github.com/ladisbuilding/alpaca-agent` (PRIVATE, `main`).** Secret-scanned what
  actually shipped: clean, 46 files, `.dev.vars` gitignored.
  ⭐ **Decision: ONE repo, private now → flip public before submission.** GitHub flips
  private→public in one click keeping full history, so "curate a separate public repo" is work with
  no benefit — and a history-less public repo reads as sanitised. The reason to start private is
  narrow but real: **git history is permanent**, this is the highest-churn phase, and a key
  committed by accident needs a history rewrite AND a key rotation. Flip ~Wed.
- ⭐⭐ **Liveness watchdog before Sentry — deliberately.** In a week-long unattended run the
  dangerous failure is **SILENCE**, not an exception: cron stops, the container fails to boot, every
  sitting returns "skipped". Nothing throws, so error reporting sees nothing and you find out
  Thursday that it stopped trading Tuesday. **Only "I expected a sitting and did not get one"
  catches that.**
  - `api/src/watchdog.ts`, hourly cron (`7 * * * *`). Alerts if no sitting in **90 min** during
    market hours; **60 min cooldown** (a watchdog that fires every 30 min trains you to ignore it).
  - Market-hours check is deliberately **WIDE** (13:30–20:00 UTC Mon–Fri): a holiday false positive
    costs one email, a narrow window costs a missed outage. Asymmetric, so err wide.
  - ✅ **PROVEN, not assumed** — `/watchdog?test=1` forces the alert path past both the hours gate
    and the cooldown. Fired for real: Mailgun 200, queued. **An alert that has never fired is not a
    proven alert; the first time it runs should not be the morning it is needed.**
  - ⚠️ From address is `watchdog@mail.careside.health` (careside's Mailgun domain, reused). Works,
    but may land in spam the first time. Fine for a self-addressed alert.
- **Sentry deliberately deferred** — it catches thrown exceptions, which is the failure mode that
  was NOT going to cost the competition. Worth adding after the Auditor and the submission package.

### 2026-08-24 (cont.) — the watchdog test found three bugs in the watchdog
Luke received the forced test alert. It landed in the inbox (not spam), and reading it surfaced
three problems — which is precisely the argument for firing an alert before you need it:
1. **Broken copy.** *"has not sat in 21 minutes ago"* — "N minutes ago" interpolated into a
   sentence that already supplied "in". A garbled alert is one you trust less.
2. **A drill was indistinguishable from a real alarm.** The test email said *"the market should be
   open"* at 5pm on a closed market. If a test and a genuine outage look the same in the inbox, the
   alert stops meaning anything on the morning it matters. Forced alerts are now prefixed
   **`[TEST]`** and say plainly that nothing is wrong.
3. ⚠️⚠️ **Worst, and invisible from the email: the forced test wrote the cooldown row.**
   Running a drill would have suppressed the next **60 minutes of REAL alerts** — testing the alarm
   would have disabled it. Only genuine alerts start the cooldown now.
⭐ **Lesson: firing the alert was worth more than writing it.** Three defects, one of which
inverted the feature, none visible from reading the code.
