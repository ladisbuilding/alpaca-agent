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
