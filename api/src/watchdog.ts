/**
 * Liveness watchdog.
 *
 * The dangerous failure in a week-long unattended run is not an exception — it is SILENCE.
 * Cron stops firing, the container fails to boot, every sitting returns "skipped": nothing
 * throws, no error is logged, and the agent simply stops trading. Error reporting cannot
 * see that. Only "I expected a sitting by now and did not get one" can.
 *
 * So this checks for absence, during the hours when a sitting is actually expected, and
 * emails once per cooldown rather than every run — a watchdog that fires every 30 minutes
 * trains you to ignore it, which is the same as not having one.
 */

type Bindings = {
  DB: D1Database
  MAILGUN_API_KEY?: string
  MAILGUN_DOMAIN?: string
  ALERT_EMAIL?: string
}

/** Minutes without a sitting before we consider the agent silent. */
const STALE_AFTER_MIN = 90
/** Minimum gap between alerts for the same condition. */
const COOLDOWN_MIN = 60

/**
 * Is the US equity market plausibly open right now?
 *
 * Deliberately approximate and deliberately WIDE: 13:30–20:00 UTC, Mon–Fri. This only
 * decides whether to expect a sitting, so a holiday false-positive costs one unnecessary
 * email. Being narrow would cost a missed outage, which is the expensive direction.
 */
function marketHoursUTC(now: Date): boolean {
  const day = now.getUTCDay()
  if (day === 0 || day === 6) return false
  const minutes = now.getUTCHours() * 60 + now.getUTCMinutes()
  return minutes >= 13 * 60 + 30 && minutes <= 20 * 60
}

async function sendAlert(env: Bindings, subject: string, body: string): Promise<string> {
  const { MAILGUN_API_KEY, MAILGUN_DOMAIN, ALERT_EMAIL } = env
  if (!MAILGUN_API_KEY || !MAILGUN_DOMAIN || !ALERT_EMAIL) {
    return 'mailgun not configured — alert logged only'
  }
  const form = new FormData()
  form.set('from', `Committee watchdog <watchdog@${MAILGUN_DOMAIN}>`)
  form.set('to', ALERT_EMAIL)
  form.set('subject', subject)
  form.set('text', body)

  const res = await fetch(`https://api.mailgun.net/v3/${MAILGUN_DOMAIN}/messages`, {
    method: 'POST',
    headers: { authorization: `Basic ${btoa(`api:${MAILGUN_API_KEY}`)}` },
    body: form,
  })
  return `${res.status} ${(await res.text()).slice(0, 120)}`
}

/**
 * @param force skip the market-hours gate and the cooldown, so the alert path can be
 *   exercised on demand. An alert that has never actually fired is not a proven alert —
 *   the first time it runs should not be the morning it is needed.
 */
export async function runWatchdog(env: Bindings, now = new Date(), force = false): Promise<string> {
  if (!force && !marketHoursUTC(now)) return 'outside market hours — not expecting a sitting'

  const latest = await env.DB.prepare(
    `SELECT started_at, trades_placed FROM cycles ORDER BY started_at DESC LIMIT 1`
  ).first<{ started_at: string; trades_placed: number }>()

  const lastSeen = latest ? new Date(latest.started_at).getTime() : 0
  const ageMin = lastSeen ? (now.getTime() - lastSeen) / 60_000 : Infinity
  if (!force && ageMin < STALE_AFTER_MIN) {
    return `ok — last sitting ${Math.round(ageMin)}m ago`
  }

  // Cooldown, so a sustained outage produces hourly nudges rather than a flood.
  const prior = force
    ? null
    : await env.DB.prepare(`SELECT last_sent FROM alerts WHERE key = 'stale'`).first<{
        last_sent: string
      }>()
  if (prior) {
    const sinceMin = (now.getTime() - new Date(prior.last_sent).getTime()) / 60_000
    if (sinceMin < COOLDOWN_MIN) return `stale (${Math.round(ageMin)}m) — within cooldown, not resending`
  }

  const human = ageMin === Infinity ? 'never' : `${Math.round(ageMin)} minutes ago`
  const result = await sendAlert(
    env,
    `⚠ Committee has not sat in ${human === 'never' ? 'any recorded session' : human}`,
    [
      `The agent has not recorded a sitting in ${human}, and the market should be open.`,
      '',
      'Nothing has necessarily thrown an error — this alert exists because the dangerous',
      'failure is silence: cron stopping, the container failing to boot, or every sitting',
      'returning "skipped".',
      '',
      'Check, in order:',
      '  1. https://alpaca-agent-runner.domfly.workers.dev/health',
      '  2. POST https://alpaca-agent-runner.domfly.workers.dev/run?force=1',
      '  3. wrangler tail alpaca-agent-runner',
      '',
      `Dashboard: https://alpaca-agent.domfly.workers.dev`,
    ].join('\n')
  )

  await env.DB.prepare(
    `INSERT INTO alerts (key, last_sent) VALUES ('stale', ?)
     ON CONFLICT(key) DO UPDATE SET last_sent = excluded.last_sent`
  )
    .bind(now.toISOString())
    .run()

  return `ALERTED — stale ${Math.round(ageMin)}m — mailgun: ${result}`
}
