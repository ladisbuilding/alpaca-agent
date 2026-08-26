/** Types mirror the Python CycleRecord in agent/src/committee/cycle.py. */

export type Gate = {
  approved: boolean
  blocked_by: string[]
  reasons: string[]
  warnings: string[]
  summary: string
}

export type Leg = {
  symbol: string
  side: 'buy' | 'sell'
  qty: number
  right: 'call' | 'put'
  strike: number
}

export type Structure = {
  underlying: string
  strategy: string
  expiry: string
  legs: Leg[]
  net_credit: number
  max_loss: number
  max_profit: number
  bid_ask_pct: number
  fingerprint: string
}

export type Deliberation = {
  nomination: { underlying: string; sleeve: string; direction: string | null; reason: string; conviction: number; source: string }
  strategy: string
  structure: Structure | Record<string, never>
  pre_gate: Gate
  debated: boolean
  bull: string | null
  bear: string | null
  bear_verdict: string | null
  risk_officer: string | null
  pm_decision: string | null
  final_gate: Gate | null
  executed: boolean
  execution_note: string | null
}

export type CycleRecord = {
  started_at: string
  finished_at: string | null
  dry_run: boolean
  market_open: boolean
  equity: number
  open_positions: number
  universe: string[]
  nominations: Deliberation['nomination'][]
  deliberations: Deliberation[]
  turns: { role: string; model: string; text: string; tool_calls: number; evidence: string[] }[]
  orders_placed: number
  cost_usd: number
  notes: string[]
}

export type Summary = {
  cycles: number
  latest_equity: number
  peak_equity: number
  llm_cost_usd: number
  distinct_structures_ordered: number
  order_rows: number
  outcomes: { outcome: string; n: number }[]
  top_blocking_gates: { gate: string; n: number }[]
}

// Same-origin: src/worker.ts proxies /api/* to the api worker over a service binding.
export const API_ORIGIN = '/api'

/**
 * A dead api must not blank the page — but it must not look like an empty state either.
 * A silent catch here turned a broken SSR fetch into "No sittings on record yet", which
 * reads as "the agent has done nothing" rather than "the dashboard is broken". The error
 * is returned so the page can say which of the two it is.
 */
export type Fetched<T> = { data: T | null; error: string | null }

export async function fetchJson<T>(path: string): Promise<Fetched<T>> {
  try {
    const res = await fetch(`${API_ORIGIN}${path}`)
    if (!res.ok) return { data: null, error: `${res.status} ${res.statusText}` }
    return { data: (await res.json()) as T, error: null }
  } catch (e) {
    return { data: null, error: e instanceof Error ? `${e.name}: ${e.message}` : String(e) }
  }
}
