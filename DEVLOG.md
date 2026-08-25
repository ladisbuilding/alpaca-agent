# alpaca-agent — Dev Log

## Current State

**Phase:** BUILT AND SELF-DRIVING. All 8 committee roles have run. **83 tests.** Everything deployed
and verified end to end. ⭐ **FRESH BUILD** — `archived-projects/` is reading material only.

**Live:**
- `https://alpaca-agent.domfly.workers.dev` — dashboard, **the hackathon's required Application URL**
- `https://alpaca-agent-api.domfly.workers.dev` — Hono + D1, ingest + watchdog cron
- `https://alpaca-agent-runner.domfly.workers.dev` — Cloudflare Container + cron, **wakes the
  committee every 30 min during US market hours. Does not depend on Luke's machine.**
- `github.com/ladisbuilding/alpaca-agent` — **PRIVATE**, flip public before submission

**Accounts:** DEV `PA35CQR61R2Q` ($100k, options L3). ⚠️ **1 of 3 paper slots left — reserved for the
brand-new dedicated submission account on launch day.**

**⚠️ Currently `DRY_RUN=true`** — it deliberates and records but places nothing. Correct for the
observation days. Flip on launch day, deliberately.

**Cost:** ~$0.24 for a cycle blocked pre-gate, **~$2.04 for one that reaches debate**. ~$25/day while
deliberating every 30 min ⇒ ~$75 of calibration data across Tue–Thu.

### Next — Tuesday at the open (09:30 ET), in order
1. **Read the overnight cycles**, then **calibrate `WIDE_SPREAD` (15%) and `THIN_CREDIT` (10%)
   against a LIVE book.** They block nearly everything on after-hours quotes. **Do not tune off
   closed-market data.** A gate blocking 100% is as broken as one blocking none.
2. ⭐⭐ **Settle whether the income sleeve's premise holds.** The committee itself showed that on
   Monday's data **IV was at or BELOW trailing realized** — i.e. no variance premium to sell. If
   that holds live, `short_delta`/DTE need rethinking. This is the biggest open question.
3. **Executor is the last untested path** — it exercises itself the first time a structure survives
   a real debate.

### Then
Wed: README + flip repo public. Thu: submission package (video ≤5min MP4, PDF deck, 16:9 cover,
public repo, demo URL). Fri 08:00 PT: fresh $100k account, swap keys, `DRY_RUN=false`.

### Settled
- ✅ **Dedicated Anthropic key in place** (2026-08-24) — in `.dev.vars` and as the container's
  Worker secret. Verified with a live cycle through the deployed container. Spend now separate
  from chaz.
- ✅ **`no_shorting`: DECIDED — leave it alone.** The Auditor recommended setting it so the broker
  enforces defined-risk-only. Rejected, deliberately:
  - ⭐ **It would not limit going both ways.** `shorting_enabled` governs shorting SHARES. The
    committee is already bidirectional **entirely through options**: bearish via
    `call_credit_spread` + `put_debit_spread`, bullish via `put_credit_spread` +
    `call_debit_spread`, neutral via `iron_condor`. Selling premium is "short options", also
    unaffected. **No structure we build needs short stock.**
  - **Marginal safety is small:** the `UNDEFINED_RISK` gate already blocks uncovered shorts, the
    executor only ever submits multi-leg defined-risk option orders, and `options_trading_level: 3`
    already blocks naked calls at the broker.
  - ⚠️ **Against that, a real unknown: how Alpaca handles ASSIGNMENT with `no_shorting` set.** An
    assigned short call leaves you briefly short shares before the long leg covers. Changing a live
    account setting to guard something already guarded, at the cost of an unresolved assignment
    interaction, is a bad trade four days out.
  - Revisit only if an equity sleeve is ever added.

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

### 2026-08-24 (cont.) — REHEARSAL: full debate path proven, and it found a strategy problem
Added `--rehearse` (`run_cycle.py`): tells the gates the market is open AND sets the clock to
mid-session, purely to exercise Bull → Bear → Risk Officer → PM → Executor before it runs
unattended. Forces dry_run, marks the record, runs locally so it never touches production data.
**Rationale: every cycle so far died at MARKET_CLOSED before the debate — four of eight roles had
never run in a real cycle, and the first unattended run was tomorrow 6:30am PT.**

⭐⭐ **The rehearsal found four bugs that reading the code did not:**
1. **`rehearse` never reached the PRE-gate** — a patch matched the final gate only. Everything still
   blocked. (The debate path stayed untested while looking tested.)
2. ⚠️ **`"Note: both expiries are 0-1 DTE..."` was parsed as a nomination for ticker `NOTE`** and
   went through the gates as a real candidate. **Fix: nominations must be IN THE UNIVERSE** — scouts
   are told to nominate from it, so anything else is a parse artifact by definition.
3. ⚠️ **A scout arguing in prose and then restating its pick counted twice** — one pick became two
   nominations, building and gating the same structure twice. **Fix: dedupe on (underlying, sleeve).**
4. ⚠️⚠️ **`"conviction 5."` silently defaulted to 3** — the trailing period means the token fails
   `isdigit()`. **Every nomination in every prior run was conviction 3.** Conviction orders which
   candidates get debated at all, so the ordering was meaningless. Now regex-parsed, with tests for
   `5.` / `4` / `(conviction: 2)` / `4/5` / absent.
All four now have regression tests (**65 passing**).

✅ **Full debate path RUNS.** SPY + QQQ iron condors reached debate; Bull, Bear, Risk Officer and PM
all executed. **Cost $2.04 for a debating cycle** (vs $0.24 when everything blocks pre-gate) —
123k input against **453k cache reads**. Executor still untested: the committee killed both, which
is correct behaviour on stale closed-market quotes.

⭐⭐⭐ **THE DEBATE FOUND A PROBLEM WITH THE STRATEGY ITSELF — this is the headline.**
- **Bull corrected its own side's evidence unprompted:** *"Honest correction to the scout: the actual
  leg IVs are 11.1%–15.4%, not 21–23%. IV/RV is ~2x, not 3x."*
- **Bear found the scout's edge was a windowing artifact:** the 13-day realized-vol window *starts
  after* the two largest days in the sample. Extend to 16 sessions and σ goes 7.5% → **11.4%
  annualized**. Verdict: *"Sold call IV is 11.08%. You are selling the near wing at or below
  trailing realized. **That is not variance premium.**"*
- **PM independently re-ran vol over 30 sessions**, produced a window-by-window table
  (13d 7.6% / 16d 11.4% / 30d 12.3%), concluded the short window was the outlier, and PASSED.
⇒ **The PM verified rather than siding with the more confident speaker.** This is the difference
between a committee and a chorus.
⚠️ **Strategy implication to test with LIVE quotes tomorrow: the income sleeve assumes IV is rich
vs realized. On this data it is NOT — it is at or below.** If that holds during market hours, the
premium sleeve has no edge as configured and `short_delta` / DTE window need rethinking.
**Do not tune off closed-market quotes; re-check at the open.**

### 2026-08-24 (cont.) — AUDITOR wired, and it found a live bug in the risk layer
- **`agent/src/committee/audit.py`** — deterministic reconciliation, no model in the loop, same
  principle as the gates: *a number a model can talk itself into is not an audit.* The Auditor
  agent reads the report and exercises judgment; it never computes the figures.
- Built to make three lies impossible to tell quietly:
  1. **Order rows are not trades.** A 4-leg condor is ONE decision. The headline always states
     decisions NEXT TO raw order rows.
  2. **Our number must reconcile against the broker's.** We attribute P&L per strategy from our own
     decision log; the account's own equity change is the independent check. The gap is reported,
     never absorbed.
  3. **A great number is a bug until proven otherwise.** Implausible win rates (≥95% at n≥5) and
     returns above a structure's own max profit are anomalies, not achievements.
- Other detectors: duplicate fingerprints (the dedup hole), fills with no decision record
  (something traded that the committee did not decide), decisions marked executed with no fills.
- ⭐ **`tests/test_audit.py` reconstructs the actual $2,015→$89 incident** — 6 identical structures
  at a 100% win rate — and asserts BOTH tells fire. A safeguard built for a specific incident is
  tested against that incident. **83 tests passing.**
- ✅ **Auditor agent run live** on `account`-only scope (11 tools, `can place orders = False`).

⭐⭐⭐ **The Auditor found a REAL BUG IN THE RISK LAYER on an empty account, before it could do harm:**
> *"Buying-power footgun, 4x. `buying_power` = $400,000 … but `options_buying_power` = $100,000.
> Defined-risk options are cash-secured. A sizing gate reading `buying_power` would over-size
> positions 4x. The binding constraint is $100,000."*
Confirmed against the live account. `PortfolioState.buying_power` was reading the **4x margin
figure**, so `INSUFFICIENT_BUYING_POWER` would have authorised **4x the intended risk**. Now uses
`options_buying_power` (fallback: cash — never the margin number), with tests.

**Three more findings from the same run, all preventive:**
- ⚠️ **`portfolio_history` is unusable for return math** — 61 of 62 daily bars read `0.0`, the last
  reads `100000.0`. Any naive return off that series yields +$100,000 or an infinite percentage.
  **P&L must come from fill activities, never the equity curve.** (We already do; now it is written
  down.) *"Benign today; catastrophic the day someone charts it."*
- ⚠️ **The activity ledger does not explain the cash balance** — $100k in `cash` with zero `CSD`
  records (paper seed, no journal entry). So `sum(activities) → equity` can NEVER reconcile on this
  account. Our reconciler uses equity CHANGE vs attributed, which is unaffected — but any future
  reconciler asserting that identity would be wrong by $100k from day one.
- 🔔 **LUKE'S CALL: the account config does not enforce the mandate.** `shorting_enabled = true`.
  Auditor recommends `no_shorting = true` so the BROKER enforces defined-risk-only rather than
  trusting our strategy layer. (`options_trading_level` 3 already blocks naked calls.) **Changing
  account settings needs Luke — not doing it unasked.**
- ⭐ **It also declared its own blind spot honestly:** *"I have no tool for open positions or working
  orders… That inference is strong but it is an inference."* — the `account`-only scope working as
  designed, and the agent saying so rather than bluffing.

### 2026-08-24 (cont.) — dashboard: the debate path was invisible
Same class of gap as the debate path itself — an untested rendering path whose first real
exercise would be tomorrow, live, with judges possibly watching. Pushed a real rehearsal record
through the actual pipeline and looked at it. Three problems:
1. ⭐⭐ **PRODUCT GAP, not just a test gap: the dashboard only ever showed the LATEST sitting.**
   Most sittings are refused pre-gate (correct and cheap), so **a judge landing on a quiet
   afternoon would see nothing but refusals while the debate transcripts — the most interesting
   thing this agent produces — sat in the database invisible.**
   ⇒ New `GET /latest-debate` (most recent cycle containing a bear verdict) + a
   **"Most recent argued case"** section, plainly timestamped rather than passed off as current.
2. **The agents write markdown**, so `**FOR — sized small…**` rendered as literal asterisks on a
   judged surface. Added a minimal inline renderer (bold + headers). Deliberately not a markdown
   library — React escapes the output and a parser is more surface than three constructs warrant.
3. **A rehearsal record was indistinguishable from a live one.** Now labelled explicitly in the
   UI: *"REHEARSAL — the gates were told the market was open… conclusions mean nothing."*
   Same lesson as the `[TEST]` alert prefix: **if a drill looks like the real thing, it will
   eventually be read as the real thing.**

### 2026-08-24 (cont.) — spend caps, because "bounded" is not the same as "capped"
Luke asked whether this could quietly cost a lot. Measured rather than reassured:
- **Observed:** $0.24 for a cycle blocked pre-gate, **$2.04** for one that debates. ~$25/day.
- **Structural worst case:** 12 turns/cycle (2 scouts + 4 debate roles × 2 survivors + 2
  executors) × ~$0.90 uncached = **~$11/cycle → ~$140/day → ~$562 by kickoff.**
- It **cannot** run away infinitely — `max_iterations=8` per turn, `max_tokens=8000`,
  `max_trades=2`, 13 crons/day are all hard bounds. ⭐ **But nothing enforced the low number, and
  the gap between $25 and $140 is real for something running unattended for a week.**

**Added:**
- `GET /spend` — today's spend, cycle count, all-time (D1).
- **`MAX_CYCLE_USD` (default $6)** — a sitting that exceeds it stops debating remaining
  candidates and says so in the record. *"A sitting that costs this much is misbehaving, not
  working hard."*
- **`DAILY_USD_CAP` (default $40)** — checked against the api BEFORE a sitting starts; over cap
  ⇒ skip. Every response now reports `spent_today_before` and `daily_cap`.
- ⚠️ **`spent_today()` returns 0.0 on failure, deliberately** — a spend check that cannot reach
  the ledger must not become the reason the agent stops trading during the competition.
  **That is exactly why the Console limit matters: it is the only HARD stop.**
- ✅ Verified live in the deployed container: `spent_today_before $2.56, daily_cap $40.0`.

⚠️ **Container rollout gotcha:** `wrangler deploy` rebuilds the image, but the RUNNING instance
persists (`sleepAfter=10m`), so the first request after a deploy can still hit the old code —
and with `max_instances: 1` the swap returns **503 "no Container instance available"** while it
provisions. **Poll `/health` until it comes back before testing a change.**

### 2026-08-25 — auto-sync (1 commits)

- market: measure IV over tradable strikes only, plus deterministic realized vol

### 2026-08-25 — the strategy failed its own tests, then the mandate changed
**First live market day.** 3 cron cycles ran unattended from the opening bell; nothing depended
on Luke's machine. $8.83 spent, no watchdog alerts. Structures reached debate for the first
time in live markets — and every single one was killed. Investigating why produced the day.

**⭐⭐⭐ The scouts were being fed a broken number.** `describe()` reported a chain-wide median
IV, polluted by deep-ITM strikes trading 1-13 contracts. That inflated SPY to 22-24% when the
strikes we would actually sell price at 13-16%. **Every nomination rested on a "3x IV/RV"
premise that did not exist**, and the Bear killed all five debates on exactly that point.
Fixed: IV measured only over quoted strikes in the 8-45 delta band, and realized vol computed
deterministically over a FIXED 30-session window so a scout cannot pick a flattering lookback.
**Measured truth: SPY 1.19x, QQQ 1.06x, IWM 1.22x — no variance premium anywhere.**

**⭐⭐ Added a deterministic regime detector** (`regime.py`): IV/RV >1.30 sell premium, <1.10 buy
it, between stand down. The premium scout now stands down explicitly — *"None of the three
underlyings meet the income sleeve's bar, so I'm standing down"* — instead of nominating on a
false premise. Added **calendar spreads** (the canonical low-IV structure), raised income
min_dte 1→2 (the assignment trap) and directional to 5-15 DTE.

**⭐⭐⭐ Re-validated ORB on 6 months of genuinely unseen data (Feb-Aug 2026).** Reimplemented
fresh in Python from the archived rules. Honest out-of-sample: **QQQ Sharpe 0.75, SPY 1.04,
IWM -1.63, TSLA 2.70** — against an archived in-sample 1.58 for QQQ. Two cautions: the archived
**symbol rankings did not hold** (it called SPY a failure; SPY is now second best — symbol
selection overfitting), and QQQ's **+0.028R/trade is too thin to survive options friction**.
⇒ Then tested whether ORB predicts anything AFTER its session: **it does not.** Hit rates
41-52%, every t-stat inside noise, TSLA actively anti-predictive by day 3. **ORB is an intraday
equity edge and cannot be wrapped in options.** Ten minutes of testing instead of a week of losses.

**⚠️ Four strategies tested, four negatives. We have no validated options edge.** Premium
selling unpaid; debit spreads are fair value minus friction; ORB intraday too thin; ORB
multi-day nonexistent.

**⭐⭐⭐ MANDATE CHANGE (Luke, 2026-08-25): deploy a small book and manage it well.** Not
"only trade proven edges". The distinction that keeps it honest: **low conviction is expressed
through SMALL SIZE, not through refusal.** Gates and defined-risk constraints unchanged. The
Bear now reserves KILL for trades that are actually BAD (mispriced tail, ignored binary,
friction eating the whole gain) rather than merely unexciting, and returns a tolerable size
otherwise. Rationale beyond P&L: the brief asks an agent to demonstrate it *"manages positions
and performs"* — an agent that never trades fails two of the four verbs outright.

**⭐⭐ Built position management** (`manage.py`) — previously we could only OPEN; positions would
run to expiry unmanaged. Deterministic exits, no model in the loop: profit target at 50% of max
profit, stop at 2x the amount at risk, time stop and **assignment-risk exit** (a short strike
within 0.5% of spot at ≤1 DTE closes regardless — *"'Defined risk' ends at 4pm"*).

**Three bugs found by running it, each of which silently inverted behaviour:**
1. ⚠️⚠️ **A negated word flipped a real decision.** The Bear wrote *"it's symmetric, not adverse,
   so **not a kill**"* and recommended ALLOW; the PM said TAKE. Recorded as **BLOCKED by
   COMMITTEE**, because the parser did `"KILL" in text.upper()`. Same class as the phantom
   `NOTE` ticker: naive substring matching on model prose. Now reads the LAST non-negated
   standalone verdict.
2. ⚠️⚠️ **NEAR_CLOSE compared a UTC clock against a 16:00 EASTERN close.** The container runs in
   UTC, so 15:48Z read as 12 minutes to the close when it was 11:48 ET, mid-session.
   **It would have blocked every afternoon entry of the competition.**
3. **The chain fetch returned only the nearest 1000 contracts (0-3 DTE)**, starving every
   longer-dated strategy — reported as NO_STRUCTURE, which reads as "no good trade" rather than
   "no data". Now fetches two expiry windows and merges.

✅ **END STATE: the full pipeline runs end to end.** QQQ and SPY put debit spreads APPROVED,
Bear ALLOW on both, final gate passed, executor reached — held only by `DRY_RUN=true`.
**122 tests.**
