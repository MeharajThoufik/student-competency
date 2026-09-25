import { useQuery } from '@tanstack/react-query'
import { Info } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Tooltip } from 'recharts'
import { api, type CompetencyScore, type ScoringConfig } from '../lib/api'
import { Card, Spinner, titleCase } from './ui'

// Categorical slot 1 (single series). Text never uses the series colour.
const SERIES = '#2a78d6'
const GRID = '#e2e8f0'

const fmt = (n: number, d = 2) => n.toFixed(d).replace(/\.?0+$/, '') || '0'

export function CompetencyProfile() {
  const data = useQuery({ queryKey: ['competencies'], queryFn: () => api.competencies() })
  const config = useQuery({ queryKey: ['scoring-config'], queryFn: api.scoringConfig, staleTime: Infinity })
  const [selected, setSelected] = useState<string | null>(null)

  if (data.isPending) return <Card title="Competency profile"><Spinner /></Card>
  if (data.error) return <Card title="Competency profile"><p className="text-sm text-rose-700">{data.error.message}</p></Card>

  const scores = data.data.scores
  const ranked = [...scores].sort((a, b) => b.score - a.score)
  const current = scores.find((s) => s.key === selected) ?? ranked[0]
  const empty = data.data.activity_count === 0

  return (
    <Card
      title="Competency profile"
      action={<span className="text-xs text-slate-500">From {data.data.activity_count} activities · as of {data.data.as_of}</span>}
    >
      {empty ? (
        <p className="text-sm text-slate-600">
          Your competency profile appears once you <Link to="/app/activities/new" className="font-medium underline">add an activity</Link>.
        </p>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="h-80" role="img" aria-label={`Radar chart of ${scores.length} competency scores out of 100`}>
            <ResponsiveContainer>
              <RadarChart data={scores} outerRadius="72%">
                <PolarGrid stroke={GRID} />
                <PolarAngleAxis dataKey="label" tick={{ fill: '#475569', fontSize: 12 }} />
                <PolarRadiusAxis domain={[0, 100]} tickCount={5} tick={{ fill: '#94a3b8', fontSize: 10 }} axisLine={false} angle={90} />
                <Radar
                  dataKey="score"
                  name="Score"
                  stroke={SERIES}
                  strokeWidth={2}
                  fill={SERIES}
                  fillOpacity={0.15}
                  dot={{ r: 4, fill: SERIES, stroke: '#fff', strokeWidth: 2 }}
                  activeDot={{ r: 6, stroke: '#fff', strokeWidth: 2 }}
                  isAnimationActive={false}
                />
                <Tooltip
                  formatter={(v) => [fmt(Number(v), 1), 'Score']}
                  contentStyle={{ borderRadius: 8, borderColor: GRID, fontSize: 12 }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          {/* Ranked list: exact values (the table view) and the selector for the breakdown */}
          <ul className="space-y-1.5">
            {ranked.map((s) => (
              <li key={s.key}>
                <button
                  onClick={() => setSelected(s.key)}
                  className={`w-full rounded-md px-2 py-1.5 text-left hover:bg-slate-50 ${current.key === s.key ? 'bg-slate-100' : ''}`}
                  aria-pressed={current.key === s.key}
                >
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium text-slate-800">{s.label}</span>
                    <span className="tabular-nums text-slate-600">{fmt(s.score, 1)}</span>
                  </div>
                  <div className="mt-1 h-1.5 rounded-full bg-slate-100">
                    <div className="h-full rounded-full" style={{ width: `${s.score}%`, background: SERIES }} />
                  </div>
                </button>
              </li>
            ))}
            <li className="px-2 pt-1 text-xs text-slate-500">Select a competency to see why it has this score.</li>
          </ul>
        </div>
      )}

      {!empty && <Breakdown score={current} config={config.data} />}
    </Card>
  )
}

function Breakdown({ score, config }: { score: CompetencyScore; config?: ScoringConfig }) {
  const [showModel, setShowModel] = useState(false)
  const desc = config?.competencies.find((c) => c.key === score.key)?.description
  const top = score.contributions.slice(0, 8)

  return (
    <div className="mt-6 border-t border-slate-100 pt-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-semibold">
          Why {score.label} is {fmt(score.score, 1)}
        </h3>
        <button onClick={() => setShowModel(!showModel)} className="inline-flex items-center gap-1 text-xs text-slate-600 hover:underline">
          <Info className="size-3.5" /> How scores are calculated
        </button>
      </div>
      {desc && <p className="mt-1 text-sm text-slate-600">{desc}</p>}

      {showModel && config && <ModelExplainer config={config} />}

      {top.length === 0 ? (
        <p className="mt-4 text-sm text-slate-500">None of your activities develop this competency yet.</p>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-slate-500">
              <tr>
                <th className="pb-2 font-medium">Activity</th>
                <th className="pb-2 text-right font-medium" title="How strongly this activity type develops the competency">Weight</th>
                <th className="pb-2 text-right font-medium" title="Outcome × level × duration">Level</th>
                <th className="pb-2 text-right font-medium" title="Self-reported 0.5 · evidence 0.8 · verified 1.0">Confidence</th>
                <th className="pb-2 text-right font-medium" title="Recency: halves every 12 months">Recency</th>
                <th className="pb-2 text-right font-medium">Points</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {top.map((c) => (
                <tr key={c.activity_id}>
                  <td className="py-2 pr-3">
                    <Link to={`/app/activities/${c.activity_id}`} className="font-medium hover:underline">
                      {c.title}
                    </Link>
                    <div className="text-xs text-slate-500">
                      {config?.activity_types[c.type_key] ?? titleCase(c.type_key)} · {c.date}
                    </div>
                  </td>
                  <td className="py-2 text-right tabular-nums">{fmt(c.weight)}</td>
                  <td className="py-2 text-right tabular-nums">×{fmt(c.level)}</td>
                  <td className="py-2 text-right tabular-nums">×{fmt(c.confidence)}</td>
                  <td className="py-2 text-right tabular-nums">×{fmt(c.decay)}</td>
                  <td className="py-2 text-right font-medium tabular-nums">{fmt(c.points, 3)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot className="text-xs text-slate-600">
              <tr>
                <td className="pt-3" colSpan={5}>
                  {score.contributions.length > top.length && `+ ${score.contributions.length - top.length} more activities · `}
                  Total points = {fmt(score.raw, 3)} → score = 100 × (1 − e<sup>−{fmt(score.raw, 3)}/{config?.k ?? 5}</sup>)
                </td>
                <td className="pt-3 text-right font-semibold tabular-nums">{fmt(score.score, 1)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
      <p className="mt-3 text-xs text-slate-500">
        Tip: attaching a certificate (×0.8) or getting it verified by an educator (×1.0) counts more than self-reporting (×0.5).
      </p>
    </div>
  )
}

function ModelExplainer({ config }: { config: ScoringConfig }) {
  const list = (o: Record<string, number>) =>
    Object.entries(o)
      .map(([k, v]) => `${titleCase(k)} ${v}`)
      .join(' · ')
  return (
    <div className="mt-3 space-y-1.5 rounded-lg bg-slate-50 p-4 text-xs text-slate-700">
      <p>
        <span className="font-semibold">points</span> = weight × level × confidence × recency, summed over your activities.
      </p>
      <p>
        <span className="font-semibold">Level</span> = outcome × scope × duration. Outcome: {list(config.outcome)}. Scope: {list(config.scope)}.
        Longer activities count up to ×2.
      </p>
      <p>
        <span className="font-semibold">Confidence</span>: {list(config.confidence)}.
      </p>
      <p>
        <span className="font-semibold">Recency</span>: halves every {config.half_life_months} months after an activity ends, so skills you
        stop using fade gradually.
      </p>
      <p>
        <span className="font-semibold">Score</span> = 100 × (1 − e<sup>−points/{config.k}</sup>): rises quickly at first, with diminishing
        returns, and never exceeds 100.
      </p>
    </div>
  )
}
