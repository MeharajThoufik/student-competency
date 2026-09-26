import { useQuery } from '@tanstack/react-query'
import { AlertTriangle } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { RISK_LABELS, SyntheticSelect } from '../../components/educator'
import { Alert, Card, Empty, Select, Spinner } from '../../components/ui'
import { api, type Cohort as CohortData, type Synthetic, type Trend } from '../../lib/api'

// Sequential blue (dataviz reference ramp) for magnitude; diverging blue↔red with a gray midpoint for trend polarity.
const BOX = '#86b6ef'
const MEDIAN = '#0d366b'
const BAR = '#2a78d6'
const TREND_ORDER: Trend[] = ['declining', 'stable', 'improving', 'emerging']
const TREND_STYLE: Record<Trend, { label: string; color: string; ink: string }> = {
  declining: { label: 'Declining', color: '#e34948', ink: '#fff' },
  stable: { label: 'Stable', color: '#d4d3cf', ink: '#0b0b0b' },
  improving: { label: 'Improving', color: '#5598e7', ink: '#fff' },
  emerging: { label: 'Emerging', color: '#1c5cab', ink: '#fff' },
  inactive: { label: 'Not started', color: '#f0efec', ink: '#52514e' },
}
const EVIDENCE_LABELS: Record<string, string> = {
  self_reported: 'Self-reported',
  evidence_attached: 'Evidence attached',
  verified: 'Verified',
  rejected: 'Rejected',
}

export function Cohort() {
  const [batch, setBatch] = useState('')
  const [synthetic, setSynthetic] = useState<Synthetic>('include')
  const params = { synthetic, ...(batch ? { batch } : {}) }
  const cohort = useQuery({ queryKey: ['cohort', params], queryFn: () => api.cohort(params) })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Cohort analytics</h1>
        <p className="text-sm text-slate-500">How the whole group is developing. Includes demo learners by default so the charts have data.</p>
      </div>
      <div className="flex flex-wrap gap-3">
        <SyntheticSelect value={synthetic} onChange={setSynthetic} />
        <Select value={batch} onChange={(e) => setBatch(e.target.value)} className="w-auto" aria-label="Batch">
          <option value="">All batches</option>
          {cohort.data?.batches.map((b) => (
            <option key={b}>{b}</option>
          ))}
        </Select>
      </div>

      {cohort.isPending ? (
        <Spinner label="Calculating cohort…" />
      ) : cohort.error ? (
        <Alert>{cohort.error.message}</Alert>
      ) : !cohort.data.learner_count ? (
        <Empty>No learners in this selection.</Empty>
      ) : (
        <CohortView data={cohort.data} />
      )}
    </div>
  )
}

function CohortView({ data }: { data: CohortData }) {
  return (
    <>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Tile label="Learners" value={data.learner_count} />
        <Tile label={`Active in last ${data.window_months} months`} value={data.active_count} />
        {Object.entries(data.risk_counts).map(([k, n]) => (
          <Link key={k} to="/app/educator/learners" title={data.risk_rules[k]} className="rounded-xl border border-slate-200 bg-white p-4 hover:border-slate-300">
            <div className="flex items-center gap-1.5 text-sm text-slate-600">
              <AlertTriangle className="size-3.5 text-amber-600" /> {RISK_LABELS[k] ?? k}
            </div>
            <div className="mt-1 text-2xl font-semibold tabular-nums">{n}</div>
          </Link>
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card title="Score spread by competency" action={<span className="text-xs text-slate-500">Learners with activities</span>}>
          <Distributions data={data} />
        </Card>
        <Card title={`Trend mix · last ${data.window_months} months`}>
          <TrendMix data={data} />
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Evidence quality">
          <Evidence data={data} />
        </Card>
        <Card title="Activity types">
          <HBars rows={data.activity_types.map((t) => ({ label: t.label, value: t.count }))} />
        </Card>
      </div>
    </>
  )
}

function Tile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="text-sm text-slate-600">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
    </div>
  )
}

/** Box plot per competency: whisker min–max, box p25–p75, median tick. */
function Distributions({ data }: { data: CohortData }) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-4 text-xs text-slate-500">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-5 rounded-sm" style={{ background: BOX }} /> Middle 50%
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-0.5" style={{ background: MEDIAN }} /> Median
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-px w-5 bg-slate-400" /> Range
        </span>
      </div>
      <ul className="space-y-2.5">
        {data.competencies.map((c) => (
          <li
            key={c.key}
            className="grid grid-cols-[9.5rem_1fr_2.5rem] items-center gap-3 text-sm"
            title={`${c.label}: min ${c.minimum} · 25% ${c.p25} · median ${c.median} · 75% ${c.p75} · max ${c.maximum} · mean ${c.mean}`}
          >
            <span className="truncate text-slate-700">{c.label}</span>
            <span className="relative h-5" role="img" aria-label={`${c.label} median ${c.median}, middle half ${c.p25} to ${c.p75}`}>
              <span className="absolute inset-y-0 left-0 right-0 my-auto h-px bg-slate-100" />
              <span className="absolute top-1/2 h-px bg-slate-400" style={{ left: `${c.minimum}%`, width: `${c.maximum - c.minimum}%` }} />
              <span className="absolute inset-y-0.5 rounded-sm" style={{ left: `${c.p25}%`, width: `${Math.max(0.5, c.p75 - c.p25)}%`, background: BOX }} />
              <span className="absolute inset-y-0 w-0.5 rounded-full" style={{ left: `calc(${c.median}% - 1px)`, background: MEDIAN }} />
            </span>
            <span className="text-right tabular-nums text-slate-600">{c.median.toFixed(0)}</span>
          </li>
        ))}
      </ul>
      <div className="mt-1 grid grid-cols-[9.5rem_1fr_2.5rem] gap-3 text-[10px] text-slate-400">
        <span />
        <span className="flex justify-between">
          <span>0</span>
          <span>50</span>
          <span>100</span>
        </span>
        <span className="text-right">median</span>
      </div>
    </div>
  )
}

/** 100% stacked bar per competency, ordered declining → emerging; "not started" is counted separately. */
function TrendMix({ data }: { data: CohortData }) {
  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
        {TREND_ORDER.map((t) => (
          <span key={t} className="inline-flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm" style={{ background: TREND_STYLE[t].color }} /> {TREND_STYLE[t].label}
          </span>
        ))}
      </div>
      <ul className="space-y-2.5">
        {data.competencies.map((c) => {
          const total = TREND_ORDER.reduce((n, t) => n + c.trends[t], 0)
          return (
            <li key={c.key} className="grid grid-cols-[9.5rem_1fr_6.5rem] items-center gap-3 text-sm">
              <span className="truncate text-slate-700">{c.label}</span>
              <span className="flex h-5 gap-0.5 overflow-hidden rounded" role="img" aria-label={`${c.label}: ${TREND_ORDER.map((t) => `${c.trends[t]} ${TREND_STYLE[t].label.toLowerCase()}`).join(', ')}`}>
                {total === 0 ? (
                  <span className="flex-1 bg-slate-100" />
                ) : (
                  TREND_ORDER.filter((t) => c.trends[t]).map((t) => {
                    const pct = (100 * c.trends[t]) / total
                    return (
                      <span
                        key={t}
                        title={`${TREND_STYLE[t].label}: ${c.trends[t]} learners (${pct.toFixed(0)}%)`}
                        className="flex items-center justify-center text-[10px] font-medium tabular-nums"
                        style={{ width: `${pct}%`, background: TREND_STYLE[t].color, color: TREND_STYLE[t].ink }}
                      >
                        {pct >= 10 ? c.trends[t] : ''}
                      </span>
                    )
                  })
                )}
              </span>
              <span className="whitespace-nowrap text-right text-xs text-slate-500" title="Learners with no score in this competency">
                {c.trends.inactive ? `+${c.trends.inactive} not started` : ''}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function Evidence({ data }: { data: CohortData }) {
  const total = Object.values(data.evidence).reduce((a, b) => a + b, 0)
  return (
    <div>
      <HBars rows={Object.entries(data.evidence).map(([k, v]) => ({ label: EVIDENCE_LABELS[k] ?? k, value: v }))} />
      {total > 0 && (
        <p className="mt-3 text-xs text-slate-500">
          {Math.round((100 * (data.evidence.evidence_attached + data.evidence.verified)) / total)}% of activities have evidence;{' '}
          {Math.round((100 * data.evidence.verified) / total)}% are verified.
        </p>
      )}
    </div>
  )
}

function HBars({ rows }: { rows: { label: string; value: number }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.value))
  return (
    <ul className="space-y-2">
      {rows.map((r) => (
        <li key={r.label} className="grid grid-cols-[9rem_1fr_3rem] items-center gap-3 text-sm">
          <span className="truncate text-slate-700">{r.label}</span>
          <span className="h-4">
            <span className="block h-full rounded-r" style={{ width: `${(100 * r.value) / max}%`, minWidth: r.value ? 2 : 0, background: BAR }} />
          </span>
          <span className="text-right tabular-nums text-slate-600">{r.value}</span>
        </li>
      ))}
    </ul>
  )
}
