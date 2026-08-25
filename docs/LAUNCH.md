# Launch day runbook — Friday 28 August 2026, 08:00 PT

The competition scores P&L across the whole window, so **every hour the agent is not trading is
score you cannot recover.** The market opens at 09:30 ET / 06:30 PT — *before* the 08:00 PT
kickoff — so the goal is to be live at the open, not at the ceremony.

This is written down because the alternative is improvising a credential swap under time
pressure while the clock runs.

---

## The one thing that must not go wrong

**The submission requires a BRAND-NEW, DEDICATED paper account.** A reused account is
disqualified, and its ID goes in the submission so judges can read the P&L.

⚠️ **Alpaca allows only 3 paper accounts and 2 are used** (`PA3CAO6AR0OV` old, `PA35CQR61R2Q`
dev). **There is exactly one slot left.** If it is spent on anything else, the submission
account cannot be created without deleting one.

⚠️ **`DRY_RUN` is already `false`.** On launch day the flag is NOT what changes — the **keys**
change. Checking the flag will tell you nothing. **Check the account number.**

---

## Pre-flight — Thursday evening

- [ ] `curl -s https://alpaca-agent-runner.domfly.workers.dev/health` → `{"ok": true}`
- [ ] `curl -s https://alpaca-agent-api.domfly.workers.dev/spend` → sane
- [ ] Dashboard loads: https://alpaca-agent.domfly.workers.dev
- [ ] Repo is **public** (judges must be able to read it) — see README
- [ ] **Flatten the dev book.** Positions on `PA35CQR61R2Q` are irrelevant to the submission
      but will confuse the Auditor's reconciliation once the keys point elsewhere. Close them,
      or accept that pre-competition decisions stay in the decision log.
- [ ] Note today's `/spend` figure so competition-window cost can be separated afterwards.

---

## Launch sequence — 06:15 PT, fifteen minutes before the open

**1. Create the account** (Luke — I cannot create accounts)

app.alpaca.markets → account switcher (top-left) → **New Paper Account**
- Nickname: `alpaca-agent COMP`
- Set Funds: **100000** — required by the rules, verify it reads exactly $100,000
- **Sync to live balance: OFF** (it would peg the account to the live $0)
- Save, then **switch into the new account** and copy its **`PA…` number**

**2. Generate keys** (Luke)

In the new account: API Keys panel → **Generate New Keys**.
⚠️ The secret is shown once and disappears on refresh. Copy both before navigating away.

**3. Swap the credentials** (me, ~2 minutes)

```bash
cd active-projects/alpaca-agent
# .dev.vars — local tooling and the audit script
#   ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY

cd container
echo -n "<KEY>"    | npx wrangler secret put ALPACA_API_KEY_ID
echo -n "<SECRET>" | npx wrangler secret put ALPACA_API_SECRET_KEY
npx wrangler deploy      # CLOUDFLARE_API_TOKEN must be UNSET — cloudchamber is OAuth-only
```

**4. Verify — the step that actually matters**

```bash
curl -s -m 400 -X POST 'https://alpaca-agent-runner.domfly.workers.dev/run?force=1'
```

Then confirm **the account number in the response is the NEW one**. Do not trust the flag, the
deploy output, or the fact that a cycle ran. A cycle running against the *dev* account looks
identical to one running against the competition account.

⚠️ **The container keeps the old instance alive for ~10 minutes after a deploy**, and with
`max_instances: 1` the swap returns `503 no Container instance available` while it provisions.
**Poll `/health` until it returns before believing a test result** — otherwise you will verify
the old image and think you are done.

**5. Confirm it is trading the right book**

```bash
cd agent && .venv/bin/python scripts/run_audit.py --no-agent
```

Expect: an empty book on a fresh account, `$100,000`, reconciles. If the Auditor reports
positions, **the keys did not swap** — the old account is still in play.

---

## During the week

- **Cron runs itself**: 13:30 UTC then every 30 min to 19:30 UTC, weekdays. First sitting lands
  exactly at the opening bell.
- **The watchdog emails** `lukedepass@gmail.com` if no sitting is recorded for 90 minutes during
  market hours. That is the alarm for silence, which is the failure that does not throw.
- **Spend caps**: $40/day, $6/cycle. Both soft — the hard stop is the Anthropic Console limit.
- **Kill switch**: set `KILL_SWITCH: "true"` in `container/wrangler.jsonc` and deploy. It blocks
  new positions AND flattens existing ones on the next cycle.

## If something breaks

| Symptom | First check |
|---|---|
| Watchdog email / no new sittings | `/health`, then `POST /run?force=1`, then `wrangler tail alpaca-agent-runner` |
| Cycles run but nothing trades | Gate names on the dashboard. `WIDE_SPREAD` / `THIN_CREDIT` blocking everything means thresholds, not market |
| Orders placed but no fills | Expected — they are limit orders. Check `/v2/orders?status=all`. Resting is not filled |
| Costs climbing | `/spend`. The daily cap stands the agent down on its own |
| Something looks too good | Run the Auditor. A number that seems excellent is a bug until proven otherwise |

## Submission checklist

- [ ] Project title, short description (≤255 chars), long description (≥100 words), tags
- [ ] Cover image — PNG/JPG, **16:9**
- [ ] Video — **MP4, max 5 minutes**; intro → walk the deck → demo the product
- [ ] Slides — **PDF**, 2–3 sentences per slide
- [ ] **Public** GitHub repo (a private one lowers the score)
- [ ] Application URL: `https://alpaca-agent.domfly.workers.dev`
- [ ] **Alpaca paper account ID — the NEW one**
- [ ] Up to 5 social links, tagging **@lablabai** and **@AlpacaHQ**

⚠️ Re-read the hackathon-specific guide at kickoff — it only unlocks on the 28th, and the
generic guidelines page carries boilerplate from other events.
