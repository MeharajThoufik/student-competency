import { useQuery } from '@tanstack/react-query'
import { ArrowDownRight, ArrowUpRight, CircleDashed, FileCheck2, Lightbulb, Minus, Plus, Sparkles, TrendingDown, TrendingUp } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { CompetencyLineChart, monthLabel, ThenNowRadar } from '../components/GrowthCharts'
import { Alert, Badge, Card, Empty, EvidenceBadge, Spinner, titleCase } from '../components/ui'
import { api, type CompetencyTrend, type Insights, type Recommendation, type Trend } from '../lib/api'

const fmt = (n: number) => n.toFixed(1)
const signed = (n: number) => `${n > 0 ? '+' : n < 0 ? '−' : '±'}${Math.abs(n).toFixed(1)}`

const TRENDS: Record<Trend, { label: string; tone: 'green' | 'blue' | 'gray' | 'red'; icon: typeof TrendingUp; hint: string }> = {
  emerging: { label: 'Emerging', tone: 'blue', icon: Sparkles, hint: 'Newly developing: low at the start of the window, now established' },
  improving: { label: 'Improving', tone: 'green', icon: TrendingUp, hint: 'Rising by at least 1 point a month' },
  stable: { label: 'Stable', tone: 'gray', icon: Minus, hint: 'Changing by less than 1 point a month' },
  declining: { label: 'Declining', tone: 'red', icon: TrendingDown, hint: 'Falling by at least 1 point a month, usually from inactivity' },
  inactive: { label: 'Not started', tone: 'gray', icon: CircleDashed, hint: 'Below 5 throughout the window' },
}

export function TrendBadge({ trend }: { trend: Trend }) {
  const t = TRENDS[trend]
  return (
    <span title={t.hint}>
      <Badge tone={t.tone}>
        <t.icon className="size-3" /> {t.label}
      </Badge>
    </span>
  )
}

export function Growth() {
  const insights = useQuery({ queryKey: ['insights'], queryFn: api.insights })
  const config = useQuery({ queryKey: ['scoring-config'], queryFn: api.scoringConfig, staleTime: Infinity })

  if (insights.isPending) return <Spinner />
  if (insights.error) return <Alert>{insights.error.message}</Alert>
  const data = insights.data
  const typeLabel = (k: string) => config.data?.activity_types[k] ?? titleCase(k)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Growth</h1>
        <p className="text-sm text-slate-500">
          How your competencies have changed over time. Trends compare the last {data.window_months} months · as of {data.as_of}
        </p>
      </div>

      {data.activity_count === 0 ? (
        <Empty>
          Your growth appears once you <Link to="/app/activities/new" className="font-medium underline">add activities</Link>. Past activities count
          too: enter their real dates and your history is rebuilt from them.
        </Empty>
      ) : (
        <>
          <TrendGrid competencies={data.competencies} cohortSize={data.cohort_size} />

          <div className="grid gap-6 xl:grid-cols-5">
            <Card title="Competencies over time" className="xl:col-span-3">
              <CompetencyLineChart insights={data} competencies={data.competencies} />
            </Card>
            <Card title="Then vs now" className="xl:col-span-2">
              <ThenNowRadar insights={data} competencies={data.competencies} />
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <StrengthsGaps data={data} />
            <Recommendations recs={data.recommendations} data={data} typeLabel={typeLabel} />
          </div>

          <LearningTimeline data={data} typeLabel={typeLabel} />
        </>
      )}

      <InterestDriftCard data={data} />
    </div>
  )
}

function TrendGrid({ competencies, cohortSize }: { competencies: CompetencyTrend[]; cohortSize: number }) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {competencies.map((c) => (
        <div key={c.key} className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex items-start justify-between gap-2">
            <span className="text-sm font-medium text-slate-700">{c.label}</span>
            <TrendBadge trend={c.trend} />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-semibold tabular-nums">{fmt(c.score)}</span>
            <span className="inline-flex items-center text-xs tabular-nums text-slate-600">
              {c.change > 0.05 ? <ArrowUpRight className="size-3.5" /> : c.change < -0.05 ? <ArrowDownRight className="size-3.5" /> : null}
              {signed(c.change)}
            </span>
          </div>
          {c.percentile != null && cohortSize > 0 && (
            <div className="mt-1 text-xs text-slate-500">Higher than {Math.round(c.percentile)}% of learners</div>
          )}
        </div>
      ))}
    </div>
  )
}

function StrengthsGaps({ data }: { data: Insights }) {
  const byKey = Object.fromEntries(data.competencies.map((c) => [c.key, c]))
  const row = (k: string) => {
    const c = byKey[k]
    return (
      <li key={k} className="flex items-center justify-between gap-2 py-1.5 text-sm">
        <span className="font-medium">{c.label}</span>
        <span className="flex items-center gap-2">
          <span className="tabular-nums text-slate-600">{fmt(c.score)}</span>
          <TrendBadge trend={c.trend} />
        </span>
      </li>
    )
  }
  return (
    <Card title="Strengths and gaps">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Strengths</h3>
      {data.strengths.length ? (
        <ul className="divide-y divide-slate-100">{data.strengths.map(row)}</ul>
      ) : (
        <p className="py-2 text-sm text-slate-500">No competency has reached 30 yet.</p>
      )}
      <h3 className="mt-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Gaps to work on</h3>
      <ul className="divide-y divide-slate-100">{data.gaps.map(row)}</ul>
      {data.cohort_size > 0 && <p className="mt-3 text-xs text-slate-500">Compared with {data.cohort_size} other learners.</p>}
    </Card>
  )
}

const REC_ICON: Record<Recommendation['kind'], ReactNode> = {
  gap: <Lightbulb className="size-4 text-amber-600" />,
  declining: <TrendingDown className="size-4 text-rose-600" />,
  evidence: <FileCheck2 className="size-4 text-sky-600" />,
}

function Recommendations({ recs, data, typeLabel }: { recs: Recommendation[]; data: Insights; typeLabel: (k: string) => string }) {
  const titles = Object.fromEntries(data.timeline.map((t) => [t.activity_id, t.title]))
  return (
    <Card title="Recommendations" action={<span className="text-xs text-slate-500">Most impact first</span>}>
      {recs.length === 0 ? (
        <p className="text-sm text-slate-500">No recommendations right now. Keep adding activities.</p>
      ) : (
        <ul className="space-y-4">
          {recs.map((r, i) => (
            <li key={i} className="flex gap-3">
              <span className="mt-0.5">{REC_ICON[r.kind]}</span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="text-sm font-semibold">{r.title}</span>
                  <span className="text-xs font-medium tabular-nums text-emerald-700">up to +{fmt(r.gain)}</span>
                </div>
                <p className="mt-0.5 text-sm text-slate-600">{r.detail}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {r.kind !== 'evidence' &&
                    r.activity_types.map((t) => (
                      <Link
                        key={t}
                        to={`/app/activities/new?type=${t}`}
                        className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-200"
                      >
                        <Plus className="size-3" /> {typeLabel(t)}
                      </Link>
                    ))}
                  {r.kind === 'evidence' &&
                    r.activity_ids.slice(0, 4).map((id) => (
                      <Link key={id} to={`/app/activities/${id}`} className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-200">
                        {titles[id] ?? `Activity ${id}`}
                      </Link>
                    ))}
                  {r.kind === 'evidence' && r.activity_ids.length > 4 && (
                    <span className="px-1 py-1 text-xs text-slate-500">+{r.activity_ids.length - 4} more</span>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function LearningTimeline({ data, typeLabel }: { data: Insights; typeLabel: (k: string) => string }) {
  const [all, setAll] = useState(false)
  const labels = Object.fromEntries(data.competencies.map((c) => [c.key, c.label]))
  const entries = all ? data.timeline : data.timeline.slice(0, 10)
  return (
    <Card title="Learning timeline" action={<span className="text-xs text-slate-500">What each activity added when you completed it</span>}>
      <ol className="relative space-y-4 border-l border-slate-200 pl-5">
        {entries.map((e) => {
          const deltas = Object.entries(e.deltas).sort((a, b) => b[1] - a[1])
          return (
            <li key={e.activity_id} className="relative">
              <span className="absolute -left-[25px] top-1.5 size-2.5 rounded-full border-2 border-white bg-slate-400" />
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <Link to={`/app/activities/${e.activity_id}`} className="text-sm font-medium hover:underline">
                  {e.title}
                </Link>
                {e.evidence_status === 'rejected' ? <Badge tone="red">Rejected</Badge> : <EvidenceBadge status={e.evidence_status} />}
              </div>
              <div className="text-xs text-slate-500">
                {typeLabel(e.type_key)} · {e.start_date}
                {e.end_date && e.end_date !== e.start_date && ` → ${e.end_date}`}
              </div>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {deltas.slice(0, 4).map(([k, v]) => (
                  <span key={k} className="rounded bg-emerald-50 px-1.5 py-0.5 text-xs text-emerald-800">
                    <span className="font-semibold tabular-nums">+{fmt(v)}</span> {labels[k]}
                  </span>
                ))}
                {deltas.length > 4 && <span className="text-xs text-slate-500">+{deltas.length - 4} more</span>}
              </div>
            </li>
          )
        })}
      </ol>
      {data.timeline.length > 10 && (
        <button onClick={() => setAll(!all)} className="mt-4 text-sm text-slate-600 hover:underline">
          {all ? 'Show fewer' : `Show all ${data.timeline.length} activities`}
        </button>
      )}
    </Card>
  )
}

function InterestDriftCard({ data }: { data: Insights }) {
  const d = data.interests
  if (!d.history.length)
    return (
      <Card title="Interest drift">
        <p className="text-sm text-slate-500">
          Add interests on the <Link to="/app/skills" className="font-medium underline">Skills & Interests</Link> page. As they change, this shows how your
          focus is shifting.
        </p>
      </Card>
    )
  const chips = (tags: string[], style: string) =>
    tags.length ? (
      tags.map((t) => (
        <span key={t} className={`rounded-full px-2.5 py-0.5 text-xs ${style}`}>
          {t}
        </span>
      ))
    ) : (
      <span className="text-xs text-slate-400">none</span>
    )
  return (
    <Card title="Interest drift" action={d.drift != null && <span className="text-sm font-semibold tabular-nums">{Math.round(d.drift * 100)}% changed</span>}>
      <p className="text-sm text-slate-600">
        {d.drift === 0
          ? `Your interests are the same as on ${d.since?.slice(0, 10)}.`
          : `Compared with ${d.since?.slice(0, 10)}: ${d.added.length} added, ${d.removed.length} dropped (Jaccard distance ${d.drift}).`}
      </p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Then · {d.since && monthLabel(d.since.slice(0, 10))}</h3>
          <div className="flex flex-wrap gap-1.5">
            {chips(d.then.filter((t) => !d.removed.includes(t)), 'bg-slate-100 text-slate-700')}
            {d.removed.map((t) => (
              <span key={t} className="rounded-full bg-slate-50 px-2.5 py-0.5 text-xs text-slate-400 line-through" title="Dropped since">
                {t}
              </span>
            ))}
          </div>
        </div>
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Now</h3>
          <div className="flex flex-wrap gap-1.5">
            {chips(d.now.filter((t) => !d.added.includes(t)), 'bg-slate-100 text-slate-700')}
            {d.added.map((t) => (
              <span key={t} className="inline-flex items-center gap-0.5 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs text-emerald-800" title="New since">
                <Plus className="size-3" /> {t}
              </span>
            ))}
          </div>
        </div>
      </div>
      <details className="mt-4 text-sm">
        <summary className="cursor-pointer text-slate-600">Full interest history ({d.history.length})</summary>
        <table className="mt-2 w-full text-left text-xs">
          <thead className="text-slate-500">
            <tr>
              <th className="py-1 font-medium">Interest</th>
              <th className="py-1 font-medium">Strength</th>
              <th className="py-1 font-medium">Added</th>
              <th className="py-1 font-medium">Removed</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {d.history.map((h, i) => (
              <tr key={i}>
                <td className="py-1">{h.tag}</td>
                <td className="py-1 tabular-nums">{h.level}/5</td>
                <td className="py-1">{h.added.slice(0, 10)}</td>
                <td className="py-1">{h.removed?.slice(0, 10) ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </Card>
  )
}
