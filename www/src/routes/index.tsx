import { createFileRoute } from '@tanstack/react-router'
import * as React from 'react'
import { fetchJson, type CycleRecord, type Deliberation, type Gate, type Summary } from '../lib/api'

export const Route = createFileRoute('/')({ component: Home })

/** Data loads on the client and refreshes itself — this is a live view of a running
 *  agent, and a stale sitting is worse than a half-second of "convening". */
function useRecord() {
  const [state, setState] = React.useState<{
    latest: CycleRecord | null
    summary: Summary | null
    debate: CycleRecord | null
    error: string | null
    loading: boolean
  }>({ latest: null, summary: null, debate: null, error: null, loading: true })

  React.useEffect(() => {
    let cancelled = false
    async function load() {
      const [latest, summary, debate] = await Promise.all([
        fetchJson<CycleRecord>('/latest'),
        fetchJson<Summary>('/summary'),
        fetchJson<CycleRecord>('/latest-debate'),
      ])
      if (cancelled) return
      setState({
        latest: latest.data,
        summary: summary.data,
        debate: debate.data,
        // /latest 404s legitimately before the first sitting; that is an empty state,
        // not a fault. Only a summary failure means the record is actually unreachable.
        error: summary.error,
        loading: false,
      })
    }
    load()
    const t = setInterval(load, 60_000)
    return () => {
      cancelled = true
      clearInterval(t)
    }
  }, [])

  return state
}

const STRATEGY_NAMES: Record<string, string> = {
  iron_condor: 'Iron condor',
  put_credit_spread: 'Put credit spread',
  call_credit_spread: 'Call credit spread',
  call_debit_spread: 'Call debit spread',
  put_debit_spread: 'Put debit spread',
  none: 'No structure',
}

function money(n: number) {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
}

function when(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** The verdict, stamped. The one place the page raises its voice. */
function Stamp({ gate, executed }: { gate: Gate | null; executed: boolean }) {
  if (executed) return <span className="stamp stamp-approved">Filled</span>
  if (!gate) return null
  if (gate.approved) return <span className="stamp stamp-approved">Approved</span>
  return <span className="stamp stamp-refused">Refused</span>
}

function Proceeding({ d }: { d: Deliberation }) {
  const gate = d.final_gate ?? d.pre_gate
  const s = 'underlying' in d.structure ? d.structure : null
  const title = STRATEGY_NAMES[d.strategy] ?? d.strategy

  return (
    <article className="document" style={{ padding: '1.75rem 1.5rem', marginBottom: '1.25rem' }}>
      <header
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: '1rem',
          flexWrap: 'wrap',
        }}
      >
        <div>
          <div className="speaker">
            {d.nomination.source.replace('_', ' ')} · conviction {d.nomination.conviction}/5
          </div>
          <h3 className="masthead" style={{ fontSize: 'clamp(1.5rem, 4vw, 2rem)', margin: '.35rem 0 0' }}>
            {d.nomination.underlying} <span style={{ fontWeight: 400 }}>{title}</span>
          </h3>
          {s && (
            <div className="machine" style={{ fontSize: 13, marginTop: '.4rem', color: '#4a4640' }}>
              {s.legs
                .map((l) => `${l.side === 'sell' ? '−' : '+'}${l.strike}${l.right[0].toUpperCase()}`)
                .join('  ')}
              {'  ·  '}
              exp {s.expiry}
            </div>
          )}
        </div>
        <Stamp gate={gate} executed={d.executed} />
      </header>

      {s && (
        <dl
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
            gap: '.75rem 1.5rem',
            margin: '1.25rem 0 0',
            paddingTop: '1rem',
            borderTop: '1px solid var(--paper-edge)',
          }}
        >
          <Figure label="Credit" value={money(s.net_credit)} />
          <Figure label="Max loss" value={money(s.max_loss)} />
          <Figure label="Spread" value={`${(s.bid_ask_pct * 100).toFixed(1)}%`} />
        </dl>
      )}

      {/* The refusal reasons, in the machine's own voice. */}
      {gate && !gate.approved && (
        <div style={{ marginTop: '1.25rem' }}>
          <div className="speaker">Blocked by</div>
          <ul style={{ margin: '.5rem 0 0', paddingLeft: '1.1rem' }}>
            {gate.reasons.map((r, i) => (
              <li key={i} style={{ marginBottom: '.35rem' }}>
                <span className="machine" style={{ fontSize: 12, color: 'var(--stamp)' }}>
                  {gate.blocked_by[i] ?? gate.blocked_by[0]}
                </span>
                <br />
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* The argument. Serif, because it is argument. */}
      {d.debated && (
        <div style={{ marginTop: '1.5rem', paddingTop: '1.25rem', borderTop: '1px solid var(--paper-edge)' }}>
          <Remark speaker="Bull" text={d.bull} />
          <Remark speaker="Bear" text={d.bear} verdict={d.bear_verdict} />
          <Remark speaker="Risk officer" text={d.risk_officer} />
          <Remark speaker="Portfolio manager" text={d.pm_decision} />
        </div>
      )}
    </article>
  )
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="speaker">{label}</dt>
      <dd className="machine" style={{ margin: '.2rem 0 0', fontSize: 18, fontWeight: 500 }}>
        {value}
      </dd>
    </div>
  )
}

/**
 * The agents write markdown — bold, headers, occasionally a table. Rendering the raw
 * asterisks on a surface judges read looks like a defect, so this handles the small subset
 * they actually use. Deliberately not a markdown library: React escapes the output, and a
 * parser here would be more surface than the three constructs warrant.
 */
function RichText({ text }: { text: string }) {
  const lines = text.split('\n')
  return (
    <>
      {lines.map((line, i) => {
        const heading = line.match(/^#{1,4}\s+(.*)$/)
        const body = heading ? heading[1] : line
        const parts = body.split(/(\*\*[^*]+\*\*)/g).filter(Boolean)
        const rendered = parts.map((p, j) =>
          p.startsWith('**') && p.endsWith('**') ? (
            <strong key={j}>{p.slice(2, -2)}</strong>
          ) : (
            <React.Fragment key={j}>{p}</React.Fragment>
          ),
        )
        if (heading) {
          return (
            <p key={i} style={{ margin: '1rem 0 .35rem', fontWeight: 600 }}>
              {rendered}
            </p>
          )
        }
        if (!line.trim()) return <br key={i} />
        return (
          <p key={i} style={{ margin: '0 0 .5rem' }}>
            {rendered}
          </p>
        )
      })}
    </>
  )
}

function Remark({ speaker, text, verdict }: { speaker: string; text: string | null; verdict?: string | null }) {
  if (!text) return null
  return (
    <div style={{ marginBottom: '1.25rem' }}>
      <div className="speaker">
        {speaker}
        {verdict && (
          <span
            className="machine"
            style={{ marginLeft: '.6rem', color: verdict === 'KILL' ? 'var(--stamp)' : 'var(--brass)' }}
          >
            {verdict}
          </span>
        )}
      </div>
      <div style={{ marginTop: '.4rem' }}>
        <RichText text={text} />
      </div>
    </div>
  )
}

function Home() {
  const { latest, summary, debate, error, loading } = useRecord()

  // The latest sitting is usually all-refused, because the gates are cheap and run first.
  // Showing only that would hide the debates entirely on a quiet afternoon — so the most
  // recent argued case gets its own section, plainly timestamped rather than passed off
  // as current.
  const debated = debate?.deliberations.filter((d) => d.debated) ?? []
  const debateIsLatest = debate?.started_at === latest?.started_at

  return (
    <main style={{ maxWidth: 860, margin: '0 auto', padding: '4rem 1.25rem 6rem' }}>
      {/* Masthead ─────────────────────────────────────────────────────────── */}
      <header style={{ marginBottom: '3rem' }}>
        <div className="eyebrow">Autonomous options committee · Alpaca paper</div>
        <h1
          className="masthead"
          style={{ fontSize: 'clamp(3rem, 12vw, 6.5rem)', margin: '.75rem 0 0' }}
        >
          The
          <br />
          Committee
        </h1>
        <p style={{ maxWidth: '46ch', marginTop: '1.5rem' }}>
          Eight agents argue about every trade. Deterministic code holds the veto — the advocates
          cannot place an order, because the tool is absent from their context. Every decision, and
          every refusal, is on the record below.
        </p>
      </header>

      <hr className="rule" />

      {/* The ledger. Deliberately not a KPI row: the two trade counts sit side by
          side because when they diverge, the dedup gate has a hole. */}
      {summary && (
        <section
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '1.5rem',
            padding: '1.75rem 0',
          }}
        >
          <Stat
            label="Equity"
            value={money(summary.latest_equity)}
            note={
              summary.peak_equity > summary.latest_equity
                ? `${money(summary.latest_equity - summary.peak_equity)} from peak`
                : 'at the high-water mark'
            }
          />
          <Stat label="Sittings" value={String(summary.cycles)} />
          <Stat
            label="Structures ordered"
            value={`${summary.distinct_structures_ordered}`}
            note={
              summary.distinct_structures_ordered === summary.order_rows
                ? `${summary.order_rows} order rows — reconciled`
                : `⚠ ${summary.order_rows} order rows — does not reconcile`
            }
          />
          <Stat label="Deliberation cost" value={`$${summary.llm_cost_usd.toFixed(2)}`} />
        </section>
      )}

      <hr className="rule" />

      {/* Latest proceeding ────────────────────────────────────────────────── */}
      <section style={{ paddingTop: '2.5rem' }}>
        <div className="eyebrow">
          Latest sitting {latest ? `· ${when(latest.started_at)}` : ''}
          {latest && !latest.market_open && ' · market closed'}
          {latest?.dry_run && ' · dry run'}
        </div>

        {loading && <p style={{ marginTop: '1rem', color: 'var(--muted)' }}>Convening…</p>}

        {!loading && !latest && error && (
          <p style={{ marginTop: '1rem', color: 'var(--stamp)' }}>
            The record is unreachable — <span className="machine">{error}</span>. This is a
            dashboard fault, not a quiet market.
          </p>
        )}

        {!loading && !latest && !error && (
          <p style={{ marginTop: '1rem' }}>
            No sittings on record yet. The committee convenes when the market opens.
          </p>
        )}

        {latest && latest.deliberations.length === 0 && (
          <p style={{ marginTop: '1rem' }}>
            The committee convened and nominated nothing. A quiet sitting is a legitimate outcome.
          </p>
        )}

        <div style={{ marginTop: '1.5rem' }}>
          {latest?.deliberations.map((d, i) => (
            <Proceeding key={i} d={d} />
          ))}
        </div>

        {latest?.notes.map((n, i) => (
          <p key={i} style={{ color: 'var(--muted)', fontSize: 15 }}>
            {n}
          </p>
        ))}
      </section>

      {/* The argument ─────────────────────────────────────────────────────── */}
      {debated.length > 0 && !debateIsLatest && (
        <section style={{ paddingTop: '3rem' }}>
          <hr className="rule" />
          <div className="eyebrow" style={{ paddingTop: '2rem' }}>
            Most recent argued case · {when(debate!.started_at)}
          </div>
          <p style={{ maxWidth: '52ch', margin: '.75rem 0 1.5rem', color: 'var(--muted)' }}>
            Most sittings are refused by the gates before anyone argues — that is the cheap
            check running first, by design. This is the last one that reached the committee.
          </p>
          {debate!.notes.some((n) => n.startsWith('REHEARSAL')) && (
            <p
              className="machine"
              style={{ fontSize: 12, color: 'var(--stamp)', margin: '0 0 1.5rem', maxWidth: '58ch' }}
            >
              REHEARSAL — the gates were told the market was open in order to exercise the debate
              path. The quotes behind this are stale, so the conclusions mean nothing. Plumbing only.
            </p>
          )}
          {debated.map((d, i) => (
            <Proceeding key={i} d={d} />
          ))}
        </section>
      )}

      {/* What the gates stopped ───────────────────────────────────────────── */}
      {summary && summary.top_blocking_gates.length > 0 && (
        <section style={{ paddingTop: '3rem' }}>
          <hr className="rule" />
          <div className="eyebrow" style={{ paddingTop: '2rem' }}>
            What the gates stopped
          </div>
          <ul style={{ listStyle: 'none', padding: 0, margin: '1rem 0 0' }}>
            {summary.top_blocking_gates.map((g) => (
              <li
                key={g.gate}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: '1rem',
                  padding: '.6rem 0',
                  borderBottom: '1px solid var(--ink-line)',
                }}
              >
                <span className="machine" style={{ fontSize: 13, color: 'var(--stamp)' }}>
                  {g.gate}
                </span>
                <span className="machine" style={{ fontSize: 13 }}>
                  {g.n}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <footer style={{ paddingTop: '4rem' }}>
        <hr className="rule" />
        <p className="eyebrow" style={{ paddingTop: '1.5rem' }}>
          Paper trading only · Alpaca × lablab.ai AI Trading Agents Hackathon
        </p>
      </footer>
    </main>
  )
}

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div>
      <div className="eyebrow">{label}</div>
      <div className="machine" style={{ fontSize: 26, marginTop: '.35rem' }}>
        {value}
      </div>
      {note && (
        <div className="machine" style={{ fontSize: 11, marginTop: '.3rem', color: 'var(--muted)' }}>
          {note}
        </div>
      )}
    </div>
  )
}
