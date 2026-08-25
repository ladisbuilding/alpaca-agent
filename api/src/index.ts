/**
 * alpaca-agent api — ingests committee cycle records, serves them to the dashboard.
 *
 * The agent container POSTs one record per cycle to /cycles. Everything else is read-only
 * and public: the dashboard is the hackathon's required Application URL, and judges need to
 * click it without a login.
 *
 * Refusals are first-class. A cycle that placed no trade is a normal, successful outcome,
 * and the reasons a structure was blocked are the most interesting thing this agent emits.
 */

import { Hono } from 'hono'
import { cors } from 'hono/cors'
import { runWatchdog } from './watchdog'

type Bindings = {
  DB: D1Database
  INGEST_TOKEN?: string
  MAILGUN_API_KEY?: string
  MAILGUN_DOMAIN?: string
  ALERT_EMAIL?: string
}

const app = new Hono<{ Bindings: Bindings }>()

// The dashboard is served from a different origin than the api, so every verb the browser
// uses must be listed — a missing method reads as a data bug, not a CORS bug.
app.use('/*', cors({ origin: '*', allowMethods: ['GET', 'POST', 'OPTIONS'] }))

app.get('/', (c) => c.json({ service: 'alpaca-agent-api', ok: true }))

/** Ingest one cycle record. Shared-secret auth: the container is the only writer. */
app.post('/cycles', async (c) => {
  const expected = c.env.INGEST_TOKEN
  if (expected) {
    const supplied = c.req.header('authorization')?.replace(/^Bearer\s+/i, '')
    if (supplied !== expected) return c.json({ error: 'unauthorized' }, 401)
  }

  let record: any
  try {
    record = await c.req.json()
  } catch {
    return c.json({ error: 'invalid json' }, 400)
  }
  if (!record?.started_at) return c.json({ error: 'record.started_at is required' }, 400)

  const id = String(record.started_at).replace(/[^0-9A-Za-z]/g, '').slice(0, 20)

  await c.env.DB.prepare(
    `INSERT OR REPLACE INTO cycles
       (id, started_at, finished_at, dry_run, market_open, equity, trades_placed, cost_usd, record)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(
      id,
      record.started_at,
      record.finished_at ?? null,
      record.dry_run ? 1 : 0,
      record.market_open ? 1 : 0,
      record.equity ?? 0,
      record.trades_placed ?? 0,
      record.cost_usd ?? 0,
      JSON.stringify(record)
    )
    .run()

  // Re-ingesting a cycle must not duplicate its decisions.
  await c.env.DB.prepare(`DELETE FROM decisions WHERE cycle_id = ?`).bind(id).run()

  const rows = (record.deliberations ?? []).map((d: any) => {
    const gate = d.final_gate ?? d.pre_gate ?? {}
    let outcome = 'refused_gate'
    if (d.executed) outcome = 'executed'
    else if (gate.blocked_by?.includes('COMMITTEE')) outcome = 'refused_committee'
    else if (gate.approved && record.dry_run) outcome = 'dry_run'
    return c.env.DB.prepare(
      `INSERT INTO decisions
         (cycle_id, underlying, strategy, fingerprint, expiry, outcome, blocked_by,
          bear_verdict, max_loss, net_credit, started_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
    ).bind(
      id,
      d.nomination?.underlying ?? '?',
      d.strategy ?? 'none',
      d.structure?.fingerprint ?? null,
      d.structure?.expiry ?? null,
      outcome,
      (gate.blocked_by ?? []).join(',') || null,
      d.bear_verdict ?? null,
      d.structure?.max_loss ?? null,
      d.structure?.net_credit ?? null,
      record.started_at
    )
  })
  if (rows.length) await c.env.DB.batch(rows)

  return c.json({ ok: true, id, decisions: rows.length })
})

/** Cycle list, newest first. Summary fields only — records are large. */
app.get('/cycles', async (c) => {
  const limit = Math.min(Number(c.req.query('limit') ?? 50), 200)
  const { results } = await c.env.DB.prepare(
    `SELECT id, started_at, finished_at, dry_run, market_open, equity, trades_placed, cost_usd
       FROM cycles ORDER BY started_at DESC LIMIT ?`
  )
    .bind(limit)
    .all()
  return c.json({ cycles: results })
})

/** One full cycle record, including every debate transcript. */
app.get('/cycles/:id', async (c) => {
  const row = await c.env.DB.prepare(`SELECT record FROM cycles WHERE id = ?`)
    .bind(c.req.param('id'))
    .first<{ record: string }>()
  if (!row) return c.json({ error: 'not found' }, 404)
  return c.json(JSON.parse(row.record))
})

/** The newest cycle — what the dashboard opens on. */
app.get('/latest', async (c) => {
  const row = await c.env.DB.prepare(
    `SELECT record FROM cycles ORDER BY started_at DESC LIMIT 1`
  ).first<{ record: string }>()
  if (!row) return c.json({ error: 'no cycles yet' }, 404)
  return c.json(JSON.parse(row.record))
})

/**
 * Headline numbers.
 *
 * Deliberately reports the DECISION count next to the raw decision-row count, and breaks
 * outcomes out rather than emitting one number. A previous system in this lineage reported
 * $2,015 at a 100% win rate that audited to $89, because duplicate rows were counted as
 * distinct trades. A single headline figure hides exactly that.
 */
app.get('/summary', async (c) => {
  const totals = await c.env.DB.prepare(
    `SELECT COUNT(*) AS cycles,
            COALESCE(SUM(trades_placed), 0) AS trades,
            COALESCE(SUM(cost_usd), 0) AS cost,
            MAX(equity) AS latest_equity
       FROM cycles`
  ).first<any>()

  const { results: byOutcome } = await c.env.DB.prepare(
    `SELECT outcome, COUNT(*) AS n FROM decisions GROUP BY outcome`
  ).all()

  const { results: byGate } = await c.env.DB.prepare(
    `SELECT blocked_by AS gate, COUNT(*) AS n
       FROM decisions WHERE blocked_by IS NOT NULL
       GROUP BY blocked_by ORDER BY n DESC LIMIT 10`
  ).all()

  const distinct = await c.env.DB.prepare(
    `SELECT COUNT(DISTINCT fingerprint) AS n FROM decisions
      WHERE outcome = 'executed' AND fingerprint IS NOT NULL`
  ).first<{ n: number }>()

  const executedRows = await c.env.DB.prepare(
    `SELECT COUNT(*) AS n FROM decisions WHERE outcome = 'executed'`
  ).first<{ n: number }>()

  return c.json({
    cycles: totals?.cycles ?? 0,
    latest_equity: totals?.latest_equity ?? 0,
    llm_cost_usd: Number(totals?.cost ?? 0),
    // These two should match. When they diverge, the same structure was entered twice and
    // the dedup gate has a hole — surfaced rather than averaged away.
    distinct_structures_traded: distinct?.n ?? 0,
    executed_decision_rows: executedRows?.n ?? 0,
    outcomes: byOutcome,
    top_blocking_gates: byGate,
  })
})

/**
 * The most recent sitting that actually held a debate.
 *
 * Most sittings are refused by the gates before any argument happens, which is correct and
 * cheap — but it means /latest is usually a quiet cycle. The debate transcripts are the most
 * interesting thing this agent produces, and without this they sit in the database invisible
 * to anyone who opens the dashboard on a slow afternoon.
 */
app.get('/latest-debate', async (c) => {
  const { results } = await c.env.DB.prepare(
    `SELECT c.record FROM cycles c
       JOIN decisions d ON d.cycle_id = c.id
      WHERE d.bear_verdict IS NOT NULL
      ORDER BY c.started_at DESC LIMIT 1`
  ).all<{ record: string }>()
  if (!results.length) return c.json({ error: 'no debates yet' }, 404)
  return c.json(JSON.parse(results[0].record))
})

/** Refusals, newest first — the dashboard's most interesting feed. */
app.get('/refusals', async (c) => {
  const { results } = await c.env.DB.prepare(
    `SELECT cycle_id, underlying, strategy, outcome, blocked_by, bear_verdict, started_at
       FROM decisions WHERE outcome LIKE 'refused%'
       ORDER BY started_at DESC LIMIT 100`
  ).all()
  return c.json({ refusals: results })
})

/** Watchdog status, so its verdict is inspectable without waiting for an email. */
app.get('/watchdog', async (c) =>
  c.json({ result: await runWatchdog(c.env, new Date(), c.req.query('test') === '1') }),
)

export default {
  fetch: app.fetch,
  /** Hourly liveness check. See src/watchdog.ts for why absence, not errors. */
  async scheduled(_event: ScheduledController, env: Bindings, ctx: ExecutionContext) {
    ctx.waitUntil(
      runWatchdog(env)
        .then((r) => console.log(`watchdog: ${r}`))
        .catch((e) => console.error('watchdog failed:', e)),
    )
  },
}
