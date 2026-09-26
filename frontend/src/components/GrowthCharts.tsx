import { useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { CompetencyTrend, Insights } from '../lib/api'

// Validated categorical palette (dataviz reference, light mode), assigned in fixed competency order so a
// competency keeps its colour whichever lines are shown. Text never uses these colours.
export const SERIES_COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948']
const THEN_COLOR = '#94a3b8'
const GRID = '#e2e8f0'
const AXIS = { fill: '#64748b', fontSize: 11 }

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
/** 'YYYY-MM-DD' → "Sep '25" without timezone shifts. */
export const monthLabel = (iso: string) => `${MONTHS[+iso.slice(5, 7) - 1]} '${iso.slice(2, 4)}`

type Props = { insights: Insights; competencies: CompetencyTrend[] }

export function CompetencyLineChart({ insights, competencies }: Props) {
  const color = (key: string) => SERIES_COLORS[competencies.findIndex((c) => c.key === key) % SERIES_COLORS.length]
  const top = [...competencies].sort((a, b) => b.score - a.score).slice(0, 4).map((c) => c.key)
  const [visible, setVisible] = useState<Set<string>>(new Set(top))
  const toggle = (k: string) => {
    const next = new Set(visible)
    if (next.has(k)) next.delete(k)
    else next.add(k)
    setVisible(next)
  }

  const { dates, scores } = insights.series
  const rows = dates.map((d, i) => ({ date: d, ...Object.fromEntries(competencies.map((c) => [c.key, scores[c.key][i]])) }))
  const label = (k: string) => competencies.find((c) => c.key === k)?.label ?? k

  return (
    <div>
      {/* Legend doubles as the series filter; names are text, colour is only the swatch */}
      <div className="mb-3 flex flex-wrap gap-1.5" role="group" aria-label="Competencies shown">
        {competencies.map((c) => {
          const on = visible.has(c.key)
          return (
            <button
              key={c.key}
              onClick={() => toggle(c.key)}
              aria-pressed={on}
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition ${
                on ? 'border-slate-300 bg-white text-slate-800' : 'border-transparent bg-slate-100 text-slate-400'
              }`}
            >
              <span className="h-0.5 w-3 rounded-full" style={{ background: on ? color(c.key) : '#cbd5e1' }} />
              {c.label}
            </button>
          )
        })}
      </div>
      <div className="h-72" role="img" aria-label={`Line chart of competency scores from ${monthLabel(dates[0])} to ${monthLabel(dates[dates.length - 1])}`}>
        <ResponsiveContainer>
          <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -16 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="date" tickFormatter={monthLabel} tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} minTickGap={24} />
            <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tick={AXIS} tickLine={false} axisLine={false} />
            <Tooltip
              cursor={{ stroke: '#94a3b8', strokeWidth: 1 }}
              content={({ active, payload, label: d }) =>
                active && payload?.length ? (
                  <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-sm">
                    <div className="mb-1 font-medium text-slate-500">{monthLabel(String(d))}</div>
                    {[...payload]
                      .sort((a, b) => Number(b.value) - Number(a.value))
                      .map((p) => (
                        <div key={String(p.dataKey)} className="flex items-center gap-2">
                          <span className="h-0.5 w-3 rounded-full" style={{ background: color(String(p.dataKey)) }} />
                          <span className="w-8 text-right font-semibold tabular-nums text-slate-900">{Number(p.value).toFixed(1)}</span>
                          <span className="text-slate-500">{label(String(p.dataKey))}</span>
                        </div>
                      ))}
                  </div>
                ) : null
              }
            />
            {competencies
              .filter((c) => visible.has(c.key))
              .map((c) => (
                <Line
                  key={c.key}
                  dataKey={c.key}
                  name={c.label}
                  stroke={color(c.key)}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, stroke: '#fff', strokeWidth: 2 }}
                  isAnimationActive={false}
                />
              ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export function ThenNowRadar({ insights, competencies }: Props) {
  const { dates, scores } = insights.series
  const available = [6, 12, 24].filter((m) => m < dates.length)
  const [months, setMonths] = useState(available[0] ?? 0)
  const last = dates.length - 1
  const thenIdx = Math.max(0, last - months)
  const data = competencies.map((c) => ({ label: c.label, then: scores[c.key][thenIdx], now: scores[c.key][last] }))

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-4 text-xs text-slate-600">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded-full" style={{ background: SERIES_COLORS[0] }} /> Now
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="w-4 border-t-2 border-dashed" style={{ borderColor: THEN_COLOR }} /> {monthLabel(dates[thenIdx])}
          </span>
        </div>
        <select
          value={months}
          onChange={(e) => setMonths(+e.target.value)}
          className="rounded-md border-0 bg-white py-1 pl-2 pr-7 text-xs ring-1 ring-inset ring-slate-300"
          aria-label="Compare with"
        >
          {available.map((m) => (
            <option key={m} value={m}>
              vs {m} months ago
            </option>
          ))}
        </select>
      </div>
      <div className="h-72" role="img" aria-label={`Radar comparing competency scores now with ${months} months ago`}>
        <ResponsiveContainer>
          <RadarChart data={data} outerRadius="70%">
            <PolarGrid stroke={GRID} />
            <PolarAngleAxis dataKey="label" tick={{ fill: '#475569', fontSize: 11 }} />
            <PolarRadiusAxis domain={[0, 100]} tickCount={5} tick={false} axisLine={false} />
            <Radar dataKey="then" name={monthLabel(dates[thenIdx])} stroke={THEN_COLOR} strokeWidth={2} strokeDasharray="4 3" fill="none" isAnimationActive={false} />
            <Radar dataKey="now" name="Now" stroke={SERIES_COLORS[0]} strokeWidth={2} fill={SERIES_COLORS[0]} fillOpacity={0.12} isAnimationActive={false} />
            <Tooltip
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-sm">
                    <div className="mb-1 font-medium text-slate-700">{String(payload[0].payload.label)}</div>
                    {payload.map((p) => (
                      <div key={String(p.dataKey)} className="flex gap-2">
                        <span className="w-8 text-right font-semibold tabular-nums text-slate-900">{Number(p.value).toFixed(1)}</span>
                        <span className="text-slate-500">{p.name}</span>
                      </div>
                    ))}
                  </div>
                ) : null
              }
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
