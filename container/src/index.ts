/**
 * The runner: wakes the committee on a schedule.
 *
 * A Worker cron fires, starts (or reuses) the container, and asks it to hold one sitting.
 * The container runs the cycle and forwards the record to the api. Nothing here depends on
 * a laptop being awake — which matters because P&L is scored across the whole competition
 * window and a missed session cannot be recovered.
 *
 * Secrets are Worker secrets, passed into the container as env vars. They are never baked
 * into the image.
 */

import { Container, getContainer } from '@cloudflare/containers'

type Env = {
  COMMITTEE: DurableObjectNamespace<Committee>
  API_ORIGIN: string
  UNIVERSE: string
  DRY_RUN: string
  MAX_TRADES: string
  KILL_SWITCH: string
  ALPACA_API_KEY_ID: string
  ALPACA_API_SECRET_KEY: string
  ANTHROPIC_API_KEY: string
  INGEST_TOKEN?: string
}

export class Committee extends Container<Env> {
  defaultPort = 8080

  // A sitting takes a few minutes at most. Sleeping soon after keeps the bill to the
  // sittings themselves rather than to idle time between them.
  sleepAfter = '10m'

  // A field, not a getter: the base class declares envVars as a property (TS2611).
  // Field initializers run after super(), so this.env is populated by here.
  envVars = {
      API_ORIGIN: this.env.API_ORIGIN,
      UNIVERSE: this.env.UNIVERSE,
      DRY_RUN: this.env.DRY_RUN,
      MAX_TRADES: this.env.MAX_TRADES,
      KILL_SWITCH: this.env.KILL_SWITCH,
      ALPACA_API_KEY_ID: this.env.ALPACA_API_KEY_ID,
      ALPACA_API_SECRET_KEY: this.env.ALPACA_API_SECRET_KEY,
      ANTHROPIC_API_KEY: this.env.ANTHROPIC_API_KEY,
      ...(this.env.INGEST_TOKEN ? { INGEST_TOKEN: this.env.INGEST_TOKEN } : {}),
  }
}

/** One sitting. Shared by the cron and the manual trigger so both take the same path. */
async function hold(env: Env, query = ''): Promise<Response> {
  const container = getContainer(env.COMMITTEE, 'committee')
  return container.fetch(new Request(`http://committee/cycle${query}`, { method: 'POST' }))
}

export default {
  /**
   * Manual control surface.
   *   GET  /health   is the container alive
   *   POST /run      hold a sitting now (?force=1 ignores market hours, ?live=1 places orders)
   */
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url)

    if (url.pathname === '/health') {
      const container = getContainer(env.COMMITTEE, 'committee')
      try {
        const res = await container.fetch(new Request('http://committee/health'))
        return new Response(await res.text(), {
          status: res.status,
          headers: { 'content-type': 'application/json' },
        })
      } catch (e) {
        return Response.json({ ok: false, error: String(e) }, { status: 503 })
      }
    }

    if (url.pathname === '/run' && request.method === 'POST') {
      const res = await hold(env, url.search)
      return new Response(await res.text(), {
        status: res.status,
        headers: { 'content-type': 'application/json' },
      })
    }

    return Response.json({
      service: 'alpaca-agent-runner',
      dry_run: env.DRY_RUN !== 'false',
      universe: env.UNIVERSE,
      endpoints: ['GET /health', 'POST /run?force=1&live=1'],
    })
  },

  /**
   * Scheduled sitting.
   *
   * Failures are logged and swallowed: one bad cron must not stop the schedule. The
   * container itself skips cheaply when the market is closed, so an out-of-hours firing
   * costs a request rather than a round of LLM calls.
   */
  async scheduled(event: ScheduledController, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(
      (async () => {
        try {
          const res = await hold(env)
          console.log(`sitting ${event.cron} -> ${res.status} ${await res.text()}`)
        } catch (e) {
          console.error(`sitting ${event.cron} failed:`, e)
        }
      })()
    )
  },
}
