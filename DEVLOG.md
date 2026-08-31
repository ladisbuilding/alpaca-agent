# alpaca-agent — Dev Log

## Current State

**Phase:** LIVE on the DEV paper account, trading for real. **145 tests.** All 8 roles have run;
every path exercised except an exit firing. ⭐ FRESH BUILD — `archived-projects/` is reading only.

**Live:** dashboard `alpaca-agent.domfly.workers.dev` (**the required Application URL**) ·
**`/deck`** (8 slides, live figures, prints to the submission PDF) · api + D1 + watchdog ·
`alpaca-agent-runner` (Container + cron, every 30 min in market hours, independent of Luke's Mac) ·
repo `github.com/ladisbuilding/alpaca-agent` — **PRIVATE, flip public before submission.**

**⚠️ `DRY_RUN=false`** — placing real orders on `PA35CQR61R2Q`. On launch day the FLAG does not
change; the **KEYS** do. **Check the account number, not the flag.** → `docs/LAUNCH.md`

⚠️ **1 of 3 paper-account slots left** — reserved for the brand-new submission account.

### ⭐⭐⭐ The headline: four strategies tested, four negatives
| Test | Result |
|---|---|
| Selling premium | IV/RV **1.05–1.22x** — not paid for the tail |
| Buying spreads at mid | mid IS fair value ⇒ EV = **minus friction** |
| ORB intraday | Sharpe **0.75** out-of-sample vs 1.58 in-sample; +0.028R/trade won't clear an options spread |
| ORB held overnight | hit **41–52%**, every t-stat inside noise — no edge at all |

**There is no validated options edge.** Independently corroborated by `IgorGanapolsky/trading`,
whose README states the same for put credits. ⇒ **Mandate is now "deploy a small book and manage
it well"**, with low conviction expressed as SMALL SIZE, not refusal.

**Cost:** ~$0.24/cycle blocked pre-gate, ~$2.04 debating. ~$26/day. Caps: $40/day, $6/cycle.

### Next
1. **Cover image** (16:9 PNG) — not started.
2. **Video** Thursday, ≤5 min MP4, with real results and real transcripts.
3. **Flip the repo public** (private lowers the score) + final secret scan.
4. Friday 06:15 PT: `docs/LAUNCH.md`.

### Open
- **No exit has fired yet** — needs a position to hit a target, stop, or 1 DTE.
- **Lessons-memory the AGENT reads** — every finding lives in git where only a human sees it.
  `IgorGanapolsky/trading` feeds curated lessons back into operations. Post-competition.

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

### 2026-08-25 (later) — README, per-strategy switches, live deck, launch runbook
- **`switches.py`** — per-family modes via `STRATEGY_MODES`: `ACTIVE` / `EXIT_ONLY` / `KILLED`.
  ⭐ **`EXIT_ONLY` stands down ENTRIES while still MANAGING what is held.** A global switch also
  stopped management, and **a position you have stopped managing is more dangerous than one you
  never opened.** Pattern borrowed from `IgorGanapolsky/trading`.
- **`README.md`** — leads with what the agent found when pointed at its own strategy, not with
  what it can do. Credits TradingAgents + IgorGanapolsky as prior art and says what differs.
- ⭐ **`/deck`** — 8 × 16:9 slides, results slide reads LIVE from the api. **Built as a page, not
  a slide file, because the figures ARE the argument and a deck exported Wednesday is stale by
  Friday.** Each slide is a print sheet with `print-color-adjust: exact`, so **printing to PDF
  produces the submission deliverable** with no separate export to drift out of sync.
- **`docs/LAUNCH.md`** — the Friday cutover written down rather than improvised under time
  pressure. Two traps recorded: `DRY_RUN` is already false so **the flag tells you nothing —
  check the account number**; and the old container survives ~10 min after deploy, so **poll
  `/health` before believing a test result** or you verify the old image.

### 2026-08-26 — auto-sync (2 commits)

- ci: run the tests, typecheck both workers, and assert the safety invariant
- api: the dashboard was showing peak equity as if it were current

### 2026-08-26 — day-trading via SINGLE options: the edge equals the friction, to the penny
Luke pushed back on the earlier dismissal of intraday directional trading, and he was right to —
**I had killed it on SPREAD friction and never tested a single option.** A spread crosses TWO
bid-asks and its mid value is small, so friction is a huge % of it. A single ATM option is ONE
leg at ~0.50 delta with a far tighter relative spread. Completely different economics.

Tested properly — ORB edge per trade, translated through a 0.50-delta option, against the REAL
measured ATM bid-ask on the live chain:

| | edge/contract | ATM friction (round trip) | net |
|---|---|---|---|
| QQQ | +$3.85 | $4.00 | **−$0.15** |
| SPY | +$3.67 | $4.00 | **−$0.33** |
| IWM | −$4.35 | $10.00 | −$14.35 |
| TSLA | +$16.56 | $51.80 (26¢ spread!) | **−$35.24** |

⭐⭐⭐ **QQQ's edge is $3.85/contract and it costs $4.00 to capture. Priced to within 15 cents.**
Not bad luck — **that is what an efficient market looks like at close range.** TSLA has 4x the
edge per trade and by far the worst spread, so it is the worst of the four.

**Honest caveats:** assumes crossing the full spread both ways (pessimistic — a mid fill would
halve it and make QQQ marginally positive, but our own limit orders have sat unfilled, so mid
fills are not free either). The 0.50-delta approximation ignores gamma (helps winners) and theta
(hurts everything held for hours). Fair summary: **a coin flip that costs you the spread.**

⇒ **Five strategies tested, five negatives** — and this is the cleanest, because it does not say
"no edge", it says **"the edge exists and equals its cost."** Far more interesting to have
measured, and the strongest single line available for the deck, video and social.

**Also today:** fixed `/summary` reporting `MAX(equity)` as `latest_equity` — the HIGH-WATER MARK
shown as a balance ($100,026 displayed while the account held $99,973). Exactly the overstatement
this project exists to prevent, in its own reporting code. Now the latest sitting's equity, with
`peak_equity` alongside and the drawdown shown.

**Added CI** (`.github/workflows/ci.yml`): 145 tests, both Workers typechecked, and a job that
asserts the least-privilege invariant so a careless toolset edit fails the build rather than a
trading morning. ⚠️ **Jobs sit QUEUED on a private repo** (Actions minutes) — flipping the repo
public makes CI free and is due today anyway.

### 2026-08-26 (research) — the regime detector was measuring at the WRONG HORIZON
Luke asked for a bigger research push: the brain, the web, competitors, past contests, outside
the box. It produced one finding that overturns Monday's conclusion.

⭐⭐⭐ **"No premium edge anywhere" was a MEASUREMENT ERROR.** I compared annualised IV against
**30-day** realised vol. Correct for a multi-week structure; **wrong for the 2-DTE structures we
actually trade.** Measured at the horizon actually traded — implied move over the structure's own
life, against how often the underlying really moved that far:

| | implied/actual σ | breached | fair ~32% | verdict |
|---|---|---|---|---|
| **IWM** 2DTE | **1.47x** | **11%** | | **STRONG seller edge** |
| **SPY** 2DTE | **1.25x** | **22%** | | seller edge |
| QQQ 2DTE | 0.96x | 30% | | fairly priced |

An ATM implied move ≈ 1σ, so fair pricing breaches ~32% of the time. **IWM breached 11%.**
⚠️ **And QQQ — the one that IS fairly priced — is what the scouts kept nominating and the
committee kept correctly refusing. The edge was in IWM all along and the detector could not see
it.**

**Caveats stated, having now been wrong in both directions:** 64 OVERLAPPING windows is not a
large independent sample; this is one IV snapshot, not a historical series; and a low breach rate
does not prove positive expectancy — losses can exceed wins per event. `THIN_CREDIT` still tests
that and stays.

**Competitor / judge intel (lablab page, re-read):**
- ⚠️ **Enrolment 2,534**, up from 2,080 on Monday.
- ⭐⭐ **JUDGES NAMED — three of five build the API:** Tony Lee (**Chief Brokerage Officer**),
  Brandon Meyerowitz (**Team Lead, Trading API**), Grace Gao (**PM**), Pawel Czech (lablab CEO),
  Chiranjeev Shah (**Technical Content Marketing**).
  ⇒ A Chief Brokerage Officer thinks about **risk and compliance** all day — deterministic gates,
  defined-risk-only and an agent that refuses is *his native language*. A content-marketing judge
  is looking for something **publishable** (Alpaca blogged about a community project, "Agent M").
  **Our honest-measurement narrative is exactly what both would want.**
- Public teams (AgentTrade AI, Team Scorpians, AgentAlpha, ALIENS, Stormers, Bagholders, quasar,
  Jetpack): descriptions are generic — "analyze markets, execute paper trades". **None mentions
  OPTIONS**, which is a CORE REQUIREMENT. Scorpians is the technically ambitious one (AMD GPUs,
  RL + transformer forecasting, live dashboard).

**Brain research — `archived-projects/stock-trader/research/unconventional-strategies.md`** is 25
researched strategies never mined. Directly relevant to a 5-day options window:
- ⭐ **0DTE breakeven iron condor** — documented parameters: 5–15 delta both sides, enter ~10:15
  ET, **Monday and Wednesday outperform**, close at 15% profit / −25% stop / 12:00 ET.
- ⭐ **Max Pain / OPEX pinning** — dealer hedging pins price near max pain; strongest in the final
  2–3 days before expiry. **Sep 4 (submission day) is a Friday weekly expiry.**
- **Earnings IV ramp** — buy the straddle 7–14d before earnings, sell before the print; profits
  from the IV ramp, never holds through the announcement. Few earnings in the window though.
- **PEAD** — noted as *"non-existent since 2006"* for large-cap US. Skip.

### 2026-08-26 (later) — regime detector rewritten; the income sleeve is trading again
Rewrote `regime.py` to measure at the horizon actually traded. **The deciding statistic is now
the BREACH RATE, not a ratio of volatilities**: an ATM implied move is ≈1σ, so fair pricing is
exceeded ~32% of the time. Fewer breaches ⇒ sellers overpaid; more ⇒ buyers overpaid. Unlike an
IV/RV ratio this compares like with like — a move the market priced, against moves that actually
happened, over **the same number of days**.
- `MarketSnapshot` now carries daily closes and `atm_iv(underlying, expiry)`; `regime()` takes
  the expiry being traded, so a price from one horizon can never be tested against moves from
  another. That was the whole bug.
- Guardrails: `MIN_WINDOWS=25` (a breach rate over a handful of windows is noise, and reporting
  noise as a verdict is how a measurement error becomes a position); missing inputs ⇒ UNKNOWN,
  never a guess. **148 tests.**
- Test fixtures build closes so a KNOWN fraction of windows breach — constructed, not simulated,
  because the breach rate is the statistic under test.

✅ **Live result, immediately:** the premium scout nominated again for the first time since
Monday, citing the corrected statistic in its own words — *"SPY — income — 1DTE implied move
1.09% vs. actual exceedance only 17% (fair ~32%)... premium is genuinely rich."*
**An IWM iron condor was APPROVED, the Bear said ALLOW, and it FILLED** (4-leg mleg at a credit).
A SPY condor filled too. 16 legs, 16 fills. The other nominations were correctly blocked by
CONCENTRATION and DUPLICATE.

⇒ **The agent is now selling premium exactly where the edge was measured to be.** Full arc:
measurement error → detected → corrected → trading the real edge.

### 2026-08-26 (cont.) — the scouts never scouted; universe was hardcoded
Luke: *"how is it that you are picking these tickers? have you heard of warrior trading? it trades
based on the news."* Both halves landed.

⚠️ **The universe was three tickers I hardcoded on day one** (`UNIVERSE: "QQQ,SPY,IWM"`). The
"scouts" chose among my guesses — and measured live, **the premium scout made ZERO tool calls in a
cycle.** `get_market_movers`, `get_most_active_stocks` and `get_news` had **never been called
once.** A market screener sat in the toolbox unopened while the agent was capped at my day-one
assumption. The regime read says IWM is rich at 1.47x; whether something else sat at 1.8x was
never asked.

**On Warrior Trading (Ross Cameron — small-cap momentum, gap scanners, low float, news catalyst,
first hour):** the *catalyst principle* transfers; **the instrument does not.** A low-float runner
has wide, thin or absent weeklies — we already measured TSLA's 26¢ ATM spread destroying a real
edge, and a small cap is far worse. So: keep the catalyst idea, apply it where options actually
trade.

**Built `screener.py`** — deterministic. Pulls most-actives + movers, **rejects on option quality
BEFORE measuring edge** (≥8 tradable strikes in the 8–45 delta band, ATM spread ≤6%), runs the
regime read on each, ranks by **breach rate**. Seeds are always included so a known-good universe
never vanishes because a screener endpoint had a bad morning. Screening failure is non-fatal.

⭐⭐⭐ **Its FIRST live run found a trap: it ranked NVDA best in the market — breach rate 0%,
implied 2-day move 8.88% — on the afternoon NVDA reported earnings.** A backward-looking breach
rate cannot see a scheduled binary. Selling that is picking up pennies in front of exactly the
tail the Bear spends its turns warning about.
⇒ **EVENT GUARD added:** the vol risk premium is a *modest, persistent* overpricing (1.2–1.6x).
When implied detaches far beyond that, the market **knows** something history cannot see. An
extreme ratio now **disqualifies** rather than ranking first. NVDA is rejected with a stated
reason. **159 tests**, incl. a fixture that verifies its own breach rate rather than being trusted.

✅ **Directional scout now uses `get_market_movers`, `get_most_active_stocks`, `get_news`** — 4
tool calls in the first live cycle, against 0 before.

### 2026-08-27 — auto-sync (1 commits)

- manage: one structure, one managed position — exits were duplicating

### 2026-08-27 — technical signals: falsified four, one survives with caveats
Luke asked whether the system takes any strategy. **Honest answer: structures yes, signals no.**
A new options STRUCTURE is one function (`chain -> Proposal`) and everything downstream works —
gates, sizing and exits are all structure-agnostic. But `build_for()` is a hardcoded if/elif over
21 sleeve-name references, and a `Nomination` carries only `(underlying, sleeve, direction,
conviction)` — **a technical signal saying "enter 294.50, stop 292, target 297" has no way to
carry those levels.** Also worth stating plainly: **`orb.py` is imported NOWHERE in the live
path.** A complete TA implementation, backtested, never connected — because its edge ($3.85/
contract) was worth less than the cost of collecting it ($4.00).

**Built `scripts/test_signals.py`** — falsifies a signal in ~10 minutes using the test that
killed ORB: measure on data postdating the idea, translate through a 0.50-delta option, charge
the REAL measured ATM spread twice.

| signal | result |
|---|---|
| gap fade | **negative everywhere.** Dead |
| intraday (open→close) | positive but t<0.7, edge < friction |
| overnight (close→open) | +0.06–0.08%, hit 55–58%, **but t≈1.0** — the archive claimed t≈17 historically, so **the anomaly has decayed**, exactly as its own source warned |
| RSI(2) reversion | the only one that clears friction |

⚠️ **One pass out of twelve tests is what multiple testing produces on its own** — the same
failure family as the "best of 288 sweep" criticised in the archived research. So it was tested
for breadth rather than believed:

**RSI(2) across 12 symbols:** significant on **TLT (t=2.22), IWM (t=2.17), EEM (t=2.14)**; flat
on QQQ/XLK/XLF/MSFT. **Pooled n=925, mean +0.09%, t=+1.79 — BELOW the conventional bar.**
⇒ **Suggestive, not established.** But the pattern is economically coherent rather than random:
it survives in small caps, emerging markets and bonds, and dies in the most heavily arbitraged
mega-cap tech. And it clears the friction bar by an order of magnitude — **IWM +$47/contract
against $8 friction**, where ORB was +$3.85 against $4.00.

⇒ Correct next step is to let the COMMITTEE argue it, with the multiple-testing objection stated
in the brief. The Bear's job is exactly that attack; surviving it is better validation than my
assertion.

### 2026-08-28 — Ross Cameron gap-and-go: the first signal with a real, robust edge
Tested market-wide and survivorship-free. **`scripts/test_gap_and_go.py`.**

My earlier note in `screener.py` argued small-cap momentum "does not transfer to an options
book" — thin, wide, often non-existent weeklies. Still true, but it only rules out trading
gappers **through options.** As **shares** it is a different question, and two things make it
live: options must be *part* of the strategy not all of it, and **at $100k PDT does not apply**
— the exact blocker that stopped the archived ORB work.

**Method.** Universe = all ~11k active US equities **plus ~2k INACTIVE ones** (a small-cap
backtest built only from survivors is biased up by precisely the pump-and-dumps that later
delisted). **SIP, not IEX** — a low-float runner is invisible in a 2% fragment of the tape;
we have SIP. Filters: gap ≥10%, price $1–20, dollar volume ≥$10M, rvol ≥5. Setup: 5-min
opening range, enter the break, stop at range low, 2:1 target, stop assumed to resolve first
when a bar spans both. **1,372 gapper-days, 1,008 triggered.**

| slippage | n | win% | mean R | t |
|---|---|---|---|---|
| 0.00% | 1008 | 44% | +0.205R | **+4.89** |
| 0.25% | 1008 | 42% | +0.126R | **+3.04** |
| 0.50% | 1008 | 41% | +0.064R | +1.56 |
| 1.00% | 1008 | 38% | −0.053R | −1.33 |

⇒ **Break-even slippage ≈0.6–0.7%.** Survivorship check: the 15 delisted setups return
**+0.119R at 0.25%** vs +0.126R for survivors — indistinguishable, so the bias is NOT driving
it. **Only ONE parameter set was tested, once** — no sweep, so no multiple-testing discount.
The 41% win rate is what a 2:1 target produces, not a defect.

⚠️ **The optimistic assumption is the STOP FILL** — modelled at the stop price plus entry-level
slippage. Real stops on a reversing gapper slip far worse, so **the true break-even is BELOW
0.6%.** Treat it as a ceiling. LULD halts unmodelled entirely.

**Comparison:** ORB edge $3.85 = friction $4.00. RSI(2) pooled t=1.79. This is t=+3.04 after
a survivorship correction. **It is the only thing tested that clears its costs with room.**

⇒ **NOT shipping it before kickoff.** Three blockers, all real: a `Nomination` carries
`(underlying, sleeve, direction, conviction)` and **cannot carry entry/stop levels**;
`verify_defined_risk()` derives max loss from **leg geometry** and has no path for a share
position; the cron is **30-minute** and this needs the 9:30–9:35 range plus entry within
minutes. Correct as a mid-contest addition with the out-of-sample work already behind it.

**Also:** CI had failed on EVERY push since the repo went public —
`ModuleNotFoundError: anthropic`, because the workflow installed only pytest while the suite
imports `committee.cycle`. Green locally against a populated `.venv`, red on every clean
checkout. Fixed; hardcoded test count dropped from the job name (second time it went stale).

### 2026-08-31 — contest withdrawn; the system is the point now
**Luke is not entering the hackathon:** *"I just want to perfect a trading system."*
`CLAUDE.md` rewritten around that. Dead: competition account, write-up, video, cover image,
social posting, `docs/LAUNCH.md`. **Stays paper** — `paper=True` is hardcoded, no live key has
ever been in this repo. ⭐ The old brief was self-contradictory (a 6-day P&L sprint rewards
YOLO and punishes risk gates); the new standard is **"would I trust this with money".**

**Cron recovered.** Fridays 5 missed sittings were Cloudflare silently not invoking the
runner's scheduled handler while firing the api worker's cron in the SAME account every hour —
and still LISTING both runner schedules as registered. Re-registering via the API appeared to
do nothing on the day but the schedule fired normally Monday; the redeploy has now
re-established triggers properly. ⭐ **A registered cron is not a scheduled cron. Prove
liveness from a SECOND worker in the same account — "registered" and "healthy" both lied.**

**Deployed the exit fixes** (committed 08-28, undeployed until now). Between those dates the
old code recorded **6 rejected closes as `closed: True` in one session**, retrying the same
blocked order every 30 min and booking success each time. A stuck limit order held the legs
(harmless in the end — IWM 293 vs a 304/309 call spread expiring worthless at max profit).

**⭐⭐⭐ THE RECORD, BY SLEEVE — the only breakdown that matters:**

| sleeve | P&L |
|---|---|
| **INCOME** (sell premium where the breach rate says rich) | **+$32 open; every closed structure green** |
| **DIRECTIONAL** (buy debit spreads on a narrative) | **−$509, 0-for-4** |

⇒ **Every dollar of the −$462 is the directional sleeve.** The income sleeve — the part driven
by a MEASURED statistic (breach rate vs the 32% fair value) — works. The part driven by an LLM
telling itself a story ("QQQ fell 6 of 7 sessions") loses. The single catalyst-sourced
directional trade (NVDA post-earnings) was the only one that behaved.
⭐ **Generalises past this project: the sleeve with a measurable premise made money; the sleeve
with a narrative premise did not.**

### 2026-08-31 (pm) — the $300/day question, answered from measurement
Luke: *"FIGURE OUT HOW TO MAKE ME 300 per DAY"* plus a mandate to go wide — gold, BTC, shorts,
swing, ORB. Did that. **Most of it failed, which is the useful part.**

**⭐⭐⭐ THE DATA-PLAN TRAP — nearly invalidated everything.** A 403 on GLD looked like rate
limiting. It was not: `"subscription does not permit querying recent SIP data"`. **SIP works
only up to YESTERDAY; live we get IEX (~2% of volume).** Every backtest so far used SIP —
i.e. **data we cannot trade on.** Rebuilt the test as a hybrid: **signal from IEX (what we
see), outcome resolved on SIP (what the market actually does to us).**

| | mean | t |
|---|---|---|
| SIP signal + SIP outcome (original backtest) | +0.178R | +1.62 |
| IEX signal + IEX outcome (flattering — sparse bars hide stop-outs) | +0.253R | +2.29 |
| **IEX signal + SIP outcome (HONEST)** | **+0.246R** | **+2.19** |

⇒ **The data plan is NOT a blocker.** IEX's sparser prints give a NARROWER opening range, so
entry is earlier and the stop tighter — a real refinement, not an artifact, because outcomes
still settle on the full tape. ⭐ **Always backtest on the feed you will actually trade on;
and an IEX-only backtest flatters itself by missing stop-outs it never printed.**

**⭐ MEASURED the real spread** on 120 gapper-days at the entry minute: median **0.627%
round trip** (p10 0.26%, p90 1.80%) vs the 0.50% modelled. Everything hinges on it:

| slippage | $/day at $284 risk | Sharpe |
|---|---|---|
| 0.25% (modelled) | +$300 | 4.23 |
| ~0.31% (measured median) | ~$230 | — |
| 0.5% + stops slipping worse | +$89 (median −$7) | 1.28 |
| 1% | **−$100** | −1.93 |

**THE WIDE SWEEP: 216 tests, FDR 10% → ZERO discoveries.** Gold, silver, miners, oil, crypto
(long-only on Alpaca — 0 of 73 pairs shortable), leveraged ETFs, trend-following, swing
momentum — **all noise.** 13 hits at p<0.05 where noise predicts ~11.

**⭐⭐⭐ THE ONE REAL FINDING — and it was PREDICTED, not mined.** The earlier 12-symbol run
claimed short-horizon mean reversion survives where arbitrage is thin. New assets confirm it:

    THIN (bonds/EM/small)   13 assets  n=951  mean +0.076%  pooled t=+3.74
    THICK (mega-cap/index)   9 assets  n=690  mean +0.053%  pooled t=+1.37

Honest core is **bonds (LQD/HYG/TLT/IEF) + international (EFA/EEM) + small caps (IWM)** —
commodities inside my "thin" label (SLV/GDX/XLU/XLE) are NEGATIVE, so **the boundary was drawn
too generously and partly after seeing the data.** EFA/EEM/IWM clear ETF friction 10-15x.

**⭐⭐⭐ THE ACTUAL ANSWER TO $300/DAY: uncorrelated streams, not more risk.**

    RSI(2) ETF basket   $150/day  Sharpe 3.87  maxDD −$2,774
    gap-and-go          ~$300/day Sharpe 3.75  maxDD −$5,468
    CORRELATION         +0.027  (essentially zero)
    combined            $452/day  Sharpe 5.55

⚠️ **Sharpe 5.55 is NOT credible** — Medallion runs ~2.5-3 net. 120 days is a short sample,
stop-fills are optimistic, and part of the asset split was post-hoc. **Expect real
degradation. The next step is to trade both small and MEASURE the decay — not to size up on
backtest numbers.**

⚠️ **"$300/day" is a MEAN, not a salary:** median +$179, **43% of days lose**, worst day
−$2,345. It is a positive-expectancy process with fat variance, not an income stream.

⭐ RSI(2) is also far EASIER to build than gap-and-go: daily bars, liquid ETFs, one decision
a day, fits the existing 30-min cron. Both still need share-position support (a `Nomination`
cannot carry levels; `verify_defined_risk()` is leg-geometry-only).

### 2026-08-31 (eve) — the SHARE SLEEVE: RSI(2) reversion, gated
Built the missing capability. `shares.py` + `reversion.py` + share primitives in `gates.py`,
20 new tests (200 total, all green).

**⚠️ The dangerous failure this is built around:** a share position has NO option legs, so
`has_uncovered_short()` returns False and `verify_defined_risk()` returns None — **a share
position would have sailed through every percentage-based gate on an unverified `max_loss`.**
That is precisely what gates.py's own docstring warns about. So a `Proposal` now refuses at
construction to be anything other than EITHER option legs OR a share leg, and shares get
their own `verify_share_risk()` re-derivation.

**Shares are NOT defined-risk and the code says so everywhere.** No long wing caps the loss.
The bound is MODELLED: `stress_move = max(8 x sigma, worst observed session)`, measured per
symbol. Over 2024-01 → 2026-08 the worst session in the basket was **EFA −6.60% (6.7 sigma)**;
IWM 4.8 sigma, TLT 3.9 — so 8 sigma sits beyond anything actually delivered.

**⭐ Sizing to RISK, not to a round number.** Position = risk_budget / (price x stress), so a
quiet bond ETF takes a bigger position than a volatile small-cap for the same downside.

**⭐⭐ THE CORRELATION FINDING — the basket is not 7 bets.**

    mean pairwise correlation 0.51    LQD/TLT/IEF: 0.89-0.92    EFA/EEM/IWM: 0.62-0.79
    => 7 assets = 1.7 EFFECTIVE INDEPENDENT BETS

On the first live scan **all six signals fired the same day, all long** (RSI(2)=0.0 across
the basket — one macro move, not six independent reads). ⭐ **I nearly added a cluster-risk
gate for this and then checked: `max_deployed_risk_pct` SUMS max_loss linearly, which IS the
perfectly-correlated worst case. It was already correct.** Summing beats root-summing here.

**⭐ A REAL HOLE, found by the scan and closed:** the per-position notional cap (25%) does not
bound the AGGREGATE. Quiet assets size to a large notional for a small modelled loss, so 12
positions could reach **~300% gross** while every position AND total risk stayed inside their
limits. Added `max_gross_share_notional_pct = 1.50` and `OpenPosition.share_notional`.

**⭐ Two bugs the tests caught immediately:**
* **A flat price series returned RSI = 100** — the usual `losses == 0 -> 100` shortcut reports
  maximum overbought on a price that never moved, and **fired a SHORT signal on a constant
  series.** No gains AND no losses is undefined = 50.
* **`scan_reversion.py` evaluated every signal against an EMPTY book**, showing six APPROVEDs
  that could never all be taken. Fixed to accumulate. ⭐ **A per-item check that never sees
  the accumulating total is not a portfolio check.**

**Live scan today:** 6 signals, all approved, **$8,981 risk (9.0% of equity), $134,972 gross
(136%)**. Under the 10% cap — but that is one correlated bet, not six.

⚠️ NOT yet wired to the committee or an executor. Next: an executor path for shares and the
1-day time-boxed exit.

### 2026-08-31 (late) — the reversion sleeve is WIRED (dry-run verified, not yet live)
Executor path, time-boxed exit, and cycle integration. 206 tests green.

**Entry timing settled first, because it decided the design:** the edge was measured entering
at the CLOSE, but the last cron sitting is 15:30 ET.

    enter at the CLOSE (backtested)      n=474  mean +0.2305%  hit 62%  t=+4.40
    enter at 15:30 ET (what we can do)   n=474  mean +0.2008%  hit 60%  t=+3.80

⇒ ~13% of the edge lost, still strongly positive. **No new infrastructure needed** — the
existing 19:30 UTC slot works, guarded by `REVERSION_FROM_ET_HOUR = 15`.

**⭐⭐ DESIGN RULING: the reversion sleeve passes the GATES but is NOT DEBATED.** The signal is
a threshold on a number. This account's own evidence: the sleeve driven by a MEASURED
statistic made money; the sleeve driven by an LLM NARRATIVE lost $509 over four trades.
Asking a model whether it likes a measured edge invites that failure back in and costs ~$1 a
sitting. Deterministic gates, no scouts, no committee.

**⭐⭐⭐ THE BUG THAT WOULD HAVE KILLED THE WHOLE SLEEVE SILENTLY.** The pass was written inline
at the end of `run_cycle` — but `if not nominations: return record` sits ABOVE it. **On any
day the option scouts nominated nothing, the entire reversion sleeve would never run** — and
a quiet options day is exactly a day it should act. Extracted to `_run_reversion()` and
called from BOTH exit paths. ⭐ **Unit tests could not see this; only the end-to-end dry run
did. An early return upstream silently disables everything written below it.**

**⭐ A second silent halving:** `MAX_TRADES=2` bounds how much an LLM-driven sleeve may do in
one sitting. The basket yields ~4 signals a day, so sharing that cap would have traded HALF
the measured strategy. Now `MAX_REVERSION_TRADES=4`, counted separately; exposure stays
bounded by the risk gates, which is the right place for it.

**Also fixed:** `_structure_dict` now serialises the share leg — without it `held_positions()`
cannot reconstruct the position, and a one-session strategy whose exit path cannot see its
own position holds forever. Six round-trip tests cover proposal → record → held → exit,
including that the exit fires on a WINNER (no target: the measured strategy takes whatever
one session gives).

**Dry run at 15:31 ET:** 6 signals, all 6 gated APPROVED, 0 executed (dry run).
⚠️ Live it would take 4, ~$6k risk. **Next: flip it live and MEASURE the decay against the
backtest.** Sharpe 3.87 is not credible; the paper fills are the experiment.

### 2026-08-31 (night) — ⚠️⚠️⚠️ RSI(2) IS FALSIFIED. The sleeve is disabled.
Luke asked *"i mean cant we backtest it?"* — and that one question killed the strategy before
it placed a single order.

**I had only ever tested Feb–Aug 2026. Alpaca has data back to 2016-01-04.**

    Feb-Aug 2026 (what it was fitted on)    n=   474   mean +0.231%   t=+4.40
    FULL 2016-2026 (the whole record)       n=10,381   mean -0.013%   t=-1.43

**NEGATIVE IN 9 OF 11 YEARS** (2017 t=-2.56, 2018 t=-2.48, 2019 t=-1.85). Only 2022 (+1.13)
and 2026 (+3.72) are positive. **2026 is the single best year in the decade and it is the one
I measured.** Per asset over full history the 2026 stars invert: LQD t=-2.90, HYG t=-2.88,
IEF t=-2.00.

**The thin/thick-arbitrage hypothesis died with it:** over full history THIN pools to
n=10,381 t=-1.43 and THICK to n=7,714 t=-1.09. **No difference at all.** The entire story was
a 2026 artifact.

**⭐⭐⭐ THE ERROR, because it is the only durable part of this:**
1. I called Feb–Aug 2026 *"out of sample"* because **the archived research ended there.**
   RSI(2) is Larry Connors' published rule from the 2000s — **out-of-sample relative to your
   own earlier work is meaningless for a rule that old.**
2. The argument that felt STRONGEST was the emptiest. *"The hypothesis predicted the pattern,
   then new assets confirmed it"* — but **the prediction and the confirmation came from the
   SAME 2026 WINDOW.** Different assets in the same period is **cross-sectional** novelty, not
   **temporal** novelty. Only the second is out-of-sample. I treated one as the other and
   found it persuasive enough to build a sleeve on.
3. I flagged "only ~6 months, one regime" as a weakness in `docs/STRATEGY-BRIEF.md` and then
   **went ahead anyway** instead of spending 20 minutes on the data that was already there.

⭐ **RULE: six months is not a backtest, it is an anecdote with a t-statistic. Test the
longest history the data allows BEFORE building anything.** `scripts/test_full_history.py`
now does it in one command.

**What stays:** the share plumbing is strategy-agnostic and all of it survives — stress-based
risk model, `verify_share_risk`, gross-exposure cap, time-boxed exit, `place_stock_order`
path, 206 tests. **What goes:** the signal. `ENABLE_REVERSION=false` by default.

**Now testing gap-and-go the same way** — it has the identical weakness (Feb–Aug 2026 only)
and deserves the identical scepticism.

### 2026-08-31 (night, cont.) — gap-and-go SURVIVES the test that killed RSI(2)
Same method, ~70 setups sampled per year, 2016–2026, at the measured 0.31% half-spread.

    2016 +0.204  2017 +0.132  2018 +0.268  2019 +0.234  2020 +0.097  2021 **-0.236**
    2022 +0.126  2023 +0.258  2024 +0.270  2025 +0.041  2026 +0.131
    ALL YEARS  n=774  mean +0.142R  t=+2.94   — POSITIVE IN 10 OF 11 YEARS

⭐ **Sampling validated internally:** the per-year sample puts 2026 at +0.131R against +0.126R
from the exhaustive 1,008-setup run. Different method, same answer.

**The contrast with RSI(2) is the whole point.** Identical test, opposite verdict:
RSI(2) negative in 9 of 11 years (pooled t=-1.43); gap-and-go positive in 10 of 11 (t=+2.94).
Six months could not tell them apart — **both looked excellent in 2026.**

⚠️ **Three caveats that keep this modest:**
1. **Early years are FLATTERED** — 2016 trades charged 2026's spread, and spreads have
   tightened a lot. First half +0.187R vs second half +0.098R; part of that "decay" is my own
   bias, not the market's.
2. **Crowding is visible:** qualifying gappers **148 (2016) → 1,748 (2025)**, twelve-fold,
   and 2025 is the weakest positive year (+0.041R).
3. **The edge still sits on its own cost** — break-even slippage ~0.6% against a measured
   0.627% median real spread. A fill-quality problem more than a signal problem.

⇒ Real, persistent, thin. **Not** the Sharpe 3.75 the 2026-only run implied.

**`docs/STRATEGY-BRIEF.md` corrected** — it had been written for Luke to send to another model
for independent review and contained the now-falsified RSI(2) claims. Retracted in place, with
the error explained, and the gap-and-go section rewritten with its full-history numbers.

### 2026-08-31 (night, cont. 2) — ⚠️ gap-and-go: THE EDGE IS ZERO AT REALISTIC FILLS
Measured the quoted spread for **every setup individually** (1,344 of 1,372) instead of
applying one median, and charged each trade its own. **Both findings are fatal.**

**⭐⭐⭐ 1. My spread-filter hypothesis was BACKWARDS.** I had written in `gapgo.py` that
"MAX_SPREAD is not a refinement — it is the strategy." **Wrong, and inverted:**

    Q1  0.00-0.37%   n=197  +0.100R  t=+1.14
    Q2  0.37-0.57%   n=198  -0.077R  t=-0.89
    Q3  0.57-0.78%   n=197  -0.060R  t=-0.65
    Q4  0.78-1.08%   n=198  +0.143R  t=+1.51
    Q5  1.09-16.4%   n=198  **+0.332R  t=+3.49**   <- the whole edge

    excluding Q5 (80% of all setups): n=790  mean +0.027R  t=+0.59  — NOTHING

**Every filter made it worse.** The edge lives exactly where execution is least trustworthy.

**⭐⭐⭐ 2. It only survives on a MIDPOINT fill.** Slippage as a multiple of each setup's own
measured spread:

    0.5x (fill at the mid)      +0.088R  t=+2.13   $205/day
    1.0x (CROSS the spread)     +0.001R  t=+0.01   **$1/day**
    1.5x (cross + adverse)      -0.087R  t=-2.22  -$204/day

**A marketable order crosses the spread. That is an edge of exactly zero.** Capping spread at
2% gives -0.012R, because the edge was in the names being excluded.

⇒ **Same shape as ORB** (edge $3.85 vs friction $4.00), which was abandoned for the same
reason. ⭐ **The pattern is now three-for-three on this project: a signal that clears a
MODELLED cost dies against the MEASURED one.**

**⭐ The methodological escalation is the reusable part.** Each layer of realism removed an
illusion, and none of the earlier layers could have caught the next:

    1. 2026 only, flat 0.25% slip          +0.126R  t=+3.04   looked excellent
    2. full 11-year history                +0.142R  t=+2.94   SURVIVED (this killed RSI(2))
    3. per-setup real spreads, mid fill     +0.088R  t=+2.13   weaker
    4. per-setup real spreads, cross        +0.001R  t=+0.01   DEAD

⭐ **"Charge friction" is not one check.** A median spread is not per-setup spread, and a
midpoint fill is not a marketable fill. Both briefs corrected in place.

**What remains open, and it is a real question rather than a rescue:** can price improvement
be obtained by RESTING a limit at the mid? That trades spread cost for adverse selection —
you fill preferentially when the move goes against you — and it cannot be modelled without
tick data, nor validated on paper (paper fills instantly at the quote, which is the exact
fiction in question).

### 2026-08-31 (night, cont. 3) — ⚠️⚠️⚠️ THE INCOME SLEEVE LOSES MONEY TOO
Luke: *"i feel like you keep flip flopping."* Fair, and the diagnosis matters more than the
defence: **every reversal moved the same way — more realism, worse result.** The failure was
PROCEDURE, not judgment. I tested sequentially and announced each intermediate result as a
verdict. Four announcements where there should have been one.

**Built `agent/scripts/validate.py` — ONE battery, run ONCE, reported ONCE.** Eight checks,
each derived from a mistake made here: full history / out-of-sample IN TIME / survivorship /
per-setup measured friction / **realistic fill that CROSSES the spread** / multiple-testing
correction / the feed you will actually trade / tail. **"Not run" counts as FAIL, and the
prior is DEAD until everything passes.**

⭐ **The asymmetry that governs all of it: a NEGATIVE result at honest costs is robust; a
POSITIVE result is never proof, only "has not failed yet."**

**Then applied it to the one strategy never tested — the LIVE income sleeve**, which is the
only thing on this account that has made money. 2024-01→2026-08 (the full option-bar history
Alpaca has), friction crossed on all 4 legs both ways, per-symbol spreads:

    ungated        n=354  mean -$26.56/condor  win 62%  t=-2.54  total -$9,404
    regime-gated   n= 70  mean -$35.56/condor  win 63%  t=-1.74   <- the GATE makes it WORSE
    IWM gross      n=120  mean +$20.01  win 72%      IWM net  -$11.99
    QQQ gross      n=116  mean -$20.42  win 56%   <- NEGATIVE BEFORE COSTS
    SPY gross      n=118  mean  -$7.97  win 64%

⭐⭐⭐ **The regime engine — the centrepiece of this system, the module I rewrote and was
pleased with — has NEGATIVE value.** Gating on "premium is rich" made every case worse.
⭐ Only IWM has gross edge, and $32 round-trip friction exceeds its +$20.
⭐ **QQQ was in the universe the whole time with no edge even before costs.**

⚠️ One nuance, NOT a rescue: the 2 condors actually closed here returned +$21/+$12 NET, close
to IWM's GROSS — so the limit orders likely got price improvement rather than crossing. On
liquid ETF options, resting inside the spread is realistic in a way it is not for a low-float
gapper. **But n=2 is not evidence.**

**⭐⭐⭐ BOTTOM LINE: four strategies, four deaths — ORB, RSI(2), gap-and-go, income sleeve.
NOTHING on this project has shown an edge that survives honest costs.** The recurring shape
every single time: **gross edge ≈ 0, and friction decides.** Cost: ~$50 of API spend and no
capital. The deliverable is the battery, which catches this in one pass instead of four.
