import { createFileRoute } from '@tanstack/react-router'
import * as React from 'react'
import { fetchJson, type Summary } from '../lib/api'

export const Route = createFileRoute('/deck')({ component: Deck })

/**
 * The submission deck, as slides.
 *
 * Built as a web page rather than in a slide tool for one reason: the numbers are live. A deck
 * exported on Wednesday is stale by Friday, and the figures here are the whole argument. The
 * page reads the same api the dashboard does.
 *
 * The submission requires a PDF. Each slide is a 16:9 sheet with a page break after it, so
 * printing to PDF from the browser produces exactly the deliverable — no separate export step
 * to drift out of sync.
 */

const SLIDE = 'deck-slide'

function Slide({
  children,
  n,
  label,
}: {
  children: React.ReactNode
  n: number
  label?: string
}) {
  return (
    <section className={SLIDE}>
      <div className="deck-inner">{children}</div>
      <footer className="deck-foot">
        <span className="eyebrow">{label ?? 'The Committee'}</span>
        <span className="machine" style={{ fontSize: 11, color: 'var(--muted)' }}>
          {String(n).padStart(2, '0')}
        </span>
      </footer>
    </section>
  )
}

function Big({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="machine" style={{ fontSize: 'clamp(1.8rem, 4vw, 3rem)', lineHeight: 1 }}>
        {value}
      </div>
      <div className="eyebrow" style={{ marginTop: '.5rem' }}>
        {label}
      </div>
    </div>
  )
}

function Deck() {
  const [summary, setSummary] = React.useState<Summary | null>(null)
  React.useEffect(() => {
    fetchJson<Summary>('/summary').then((r) => setSummary(r.data))
  }, [])

  const refusals =
    summary?.outcomes
      .filter((o) => o.outcome.startsWith('refused'))
      .reduce((a, o) => a + o.n, 0) ?? 0
  const total = summary?.outcomes.reduce((a, o) => a + o.n, 0) ?? 0

  return (
    <main className="deck">
      {/* 1 — the thesis */}
      <Slide n={1}>
        <div className="eyebrow">Alpaca × lablab.ai · AI Trading Agents Hackathon</div>
        <h1 className="masthead" style={{ fontSize: 'clamp(2.5rem, 7vw, 5rem)', margin: '1rem 0' }}>
          The Committee
        </h1>
        <p style={{ fontSize: '1.15rem', maxWidth: '30ch' }}>
          Eight AI agents argue about every trade. Deterministic code holds the veto.
        </p>
        <p style={{ color: 'var(--muted)', marginTop: '1.5rem' }}>
          An autonomous options desk that knows when <em>not</em> to trade.
        </p>
      </Slide>

      {/* 2 — the problem */}
      <Slide n={2} label="Problem">
        <div className="eyebrow">The problem</div>
        <h2 className="masthead" style={{ fontSize: 'clamp(1.6rem, 4vw, 2.6rem)', margin: '.75rem 0 1.5rem' }}>
          Trading agents are built to find trades.
          <br />
          Almost none are built to tell you there isn't one.
        </h2>
        <p style={{ maxWidth: '46ch' }}>
          An LLM asked to find an opportunity will always find one. That is the failure mode: a
          confident narrative wrapped around no edge, sized as though the narrative were
          evidence.
        </p>
        <p style={{ maxWidth: '46ch', marginTop: '1rem', color: 'var(--muted)' }}>
          A predecessor in this lineage reported <strong>$2,015 at a 100% win rate</strong>.
          Audited, it had made <strong>$89</strong>.
        </p>
      </Slide>

      {/* 3 — what it found */}
      <Slide n={3} label="Finding">
        <div className="eyebrow">What it found — pointed at its own strategy</div>
        <table className="deck-table">
          <tbody>
            <tr>
              <td>Selling premium</td>
              <td className="machine">IV/RV 1.05–1.22x</td>
              <td>not paid for the tail</td>
            </tr>
            <tr>
              <td>Buying spreads at mid</td>
              <td className="machine">EV = −friction</td>
              <td>mid <em>is</em> fair value</td>
            </tr>
            <tr>
              <td>Opening-range breakout</td>
              <td className="machine">Sharpe 0.75</td>
              <td>vs 1.58 claimed in-sample</td>
            </tr>
            <tr>
              <td>ORB held overnight</td>
              <td className="machine">hit 41–52%</td>
              <td>every t-stat inside noise</td>
            </tr>
          </tbody>
        </table>
        <p style={{ marginTop: '1.5rem', maxWidth: '48ch' }}>
          The inherited research claimed <strong>Sharpe 3.31</strong>. That was the best of a
          288-combination sweep, never itself validated. Re-run on six months of data that did
          not exist when those parameters were chosen: <strong>0.75</strong>.
        </p>
      </Slide>

      {/* 4 — the design */}
      <Slide n={4} label="Design">
        <div className="eyebrow">Three commitments</div>
        <ol className="deck-list">
          <li>
            <strong>Deterministic code holds the veto.</strong> The LLM never picks a strike,
            sizes past a cap, or places an ungated order. A number a model can talk itself into
            is not a number.
          </li>
          <li>
            <strong>Capability is infrastructure, not prompting.</strong> Each agent runs its own
            MCP server scoped by <span className="machine">ALPACA_TOOLSETS</span>. The advocates
            get 39 tools, <strong>zero</strong> can place an order. The Bear is not told not to
            trade — it has no hands.
          </li>
          <li>
            <strong>A refusal is a result.</strong> Most sittings end without a trade, and the
            record leads with why.
          </li>
        </ol>
      </Slide>

      {/* 5 — the room */}
      <Slide n={5} label="Architecture">
        <div className="eyebrow">How a sitting runs</div>
        <pre className="deck-flow">{`snapshot ─→ manage open positions ─→ scouts nominate
                                          │
                                  deterministic build
                                          │
                                   PRE-GATE  ($0.24)
                                          │
                          bull ⇄ bear ⇄ risk officer ⇄ PM   ($2.04)
                                          │
                                  FINAL GATE  (binding)
                                          │
                              executor ─→ decision record`}</pre>
        <p style={{ marginTop: '1.25rem', maxWidth: '52ch' }}>
          Exits run first — freeing risk beats adding to the book. Gates run before the debate —
          a structure already rejected is not worth $3 of argument. Everything is argued from one
          immutable snapshot.
        </p>
      </Slide>

      {/* 6 — honest P&L */}
      <Slide n={6} label="Audit">
        <div className="eyebrow">Three lies it cannot tell</div>
        <ol className="deck-list">
          <li>
            <strong>Order rows are not trades.</strong> A four-leg condor is one decision. The
            headline always states decisions beside raw order rows.
          </li>
          <li>
            <strong>Our number reconciles against the broker's.</strong> Attribution comes from
            our log; the account's own equity change is the check. The gap is reported, never
            absorbed.
          </li>
          <li>
            <strong>A great number is a bug until proven otherwise.</strong> Win rates ≥95%, or
            returns above a defined-risk structure's own maximum, are anomalies.
          </li>
        </ol>
        <p style={{ marginTop: '1.25rem', color: 'var(--muted)', maxWidth: '50ch' }}>
          The first live run reported "2 trades placed" while the broker showed zero fills — both
          were resting limit orders. Nothing here may call an order a trade.
        </p>
      </Slide>

      {/* 7 — live numbers */}
      <Slide n={7} label="Results">
        <div className="eyebrow">Live · read from the running agent</div>
        <div className="deck-stats">
          <Big value={String(summary?.cycles ?? '—')} label="Sittings held" />
          <Big value={String(refusals)} label="Refusals on record" />
          <Big
            value={total ? `${Math.round((refusals / total) * 100)}%` : '—'}
            label="Declined"
          />
          <Big
            value={summary ? `$${summary.llm_cost_usd.toFixed(2)}` : '—'}
            label="Deliberation cost"
          />
        </div>
        <p style={{ marginTop: '2rem', maxWidth: '48ch' }}>
          Most sittings end in a refusal, each with a named gate and a reason. That is the
          product working, not failing.
        </p>
        <p className="machine" style={{ fontSize: 12, marginTop: '1rem', color: 'var(--muted)' }}>
          alpaca-agent.domfly.workers.dev
        </p>
      </Slide>

      {/* 8 — close */}
      <Slide n={8} label="Close">
        <h2 className="masthead" style={{ fontSize: 'clamp(1.8rem, 5vw, 3rem)', maxWidth: '20ch' }}>
          The unglamorous skill is knowing when not to trade.
        </h2>
        <p style={{ marginTop: '1.5rem', maxWidth: '46ch' }}>
          This agent measures whether its edge exists today, sizes to the conviction it actually
          has, manages what it holds, and audits its own results against the broker.
        </p>
        <p style={{ marginTop: '1.5rem', color: 'var(--muted)' }}>
          Paper trading only. Every figure here is measured, including the ones that say the
          strategy did not work.
        </p>
      </Slide>

      <div className="deck-hint">
        Print this page to PDF for the submission deck — each slide is a 16:9 sheet.
      </div>
    </main>
  )
}
