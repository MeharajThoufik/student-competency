import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Sankey,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { LinkProps, NodeProps } from 'recharts/types/chart/Sankey'
import { DemoBadge, SyntheticSelect } from '../../components/educator'
import { monthLabel, SERIES_COLORS } from '../../components/GrowthCharts'
import { Alert, Card, Select, Spinner, titleCase } from '../../components/ui'
import { api, type Grouping, type Synthetic } from '../../lib/api'

// Group identity = colour AND marker shape (a scatter with >3 colours needs secondary encoding).
const SHAPES = ['circle', 'square', 'triangle', 'diamond', 'star', 'cross', 'wye', 'circle'] as const
const GLYPH = ['●', '■', '▲', '◆', '★', '✚', 'Y', '○']
const INACTIVE_COLOR = '#c9c8c3'
const GRID = '#e2e8f0'
const AXIS = { fill: '#64748b', fontSize: 11 }
const color = (g: number) => (g < 0 ? INACTIVE_COLOR : SERIES_COLORS[g % SERIES_COLORS.length])
const f2 = (v: number | null | undefined) => (v == null ? '—' : v.toFixed(2))

export function Groups() {
  const [synthetic, setSynthetic] = useState<Synthetic>('include')
  const [k, setK] = useState('')
  const params = { synthetic, ...(k ? { k } : {}) }
  const q = useQuery({ queryKey: ['groups', params], queryFn: () => api.groups(params) })
  const config = useQuery({ queryKey: ['scoring-config'], queryFn: api.scoringConfig, staleTime: Infinity })
  const compLabel = (key: string) => config.data?.competencies.find((c) => c.key === key)?.label ?? titleCase(key)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Learner groups</h1>
        <p className="text-sm text-slate-500">
          Learners grouped by the <em>shape</em> of their competency profile (what they focus on) and how active they are, and how they move between
          groups over the past year.
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <SyntheticSelect value={synthetic} onChange={setSynthetic} />
        <Select value={k} onChange={(e) => setK(e.target.value)} className="w-auto" aria-label="Number of groups">
          <option value="">Groups: automatic</option>
          {[2, 3, 4, 5, 6, 7, 8].map((n) => (
            <option key={n} value={n}>
              {n} groups
            </option>
          ))}
        </Select>
      </div>

      {q.isPending ? (
        <Spinner label="Clustering learners…" />
      ) : q.error ? (
        <Alert>{q.error.message}</Alert>
      ) : (
        <GroupsView g={q.data} compLabel={compLabel} />
      )}
    </div>
  )
}

function GroupsView({ g, compLabel }: { g: Grouping; compLabel: (k: string) => string }) {
  const [open, setOpen] = useState<number | null>(null)
  const now = g.period_dates.length - 1
  const active = g.members.filter((m) => m.states[now] >= 0)
  const inactive = g.members.length - active.length

  return (
    <>
      <p className="text-sm text-slate-600">
        <span className="font-semibold">{g.k} groups</span> among {active.length} active learners
        {inactive > 0 && ` (${inactive} not active yet)`}. {g.notes.join(' ')}
        {g.movement_rate != null && ` ${Math.round(100 * g.movement_rate)}% of learners changed group since ${monthLabel(g.period_dates[0])}.`}
      </p>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {g.groups.map((gr) => {
          const members = active.filter((m) => m.states[now] === gr.id)
          return (
            <Card key={gr.id}>
              <div className="flex items-start gap-2">
                <span className="text-lg leading-5" style={{ color: color(gr.id) }} aria-hidden>
                  {GLYPH[gr.id]}
                </span>
                <div className="min-w-0 flex-1">
                  <h3 className="font-semibold leading-5">{gr.name}</h3>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {gr.size} learners · {Math.round((100 * gr.size) / Math.max(1, active.length))}%
                  </p>
                </div>
              </div>
              <ul className="mt-3 space-y-1">
                {Object.entries(gr.mean_scores).map(([key, v]) => (
                  <li key={key} className="grid grid-cols-[7.5rem_1fr_2rem] items-center gap-2 text-xs">
                    <span className={`truncate ${gr.defining.includes(key) ? 'font-semibold text-slate-900' : 'text-slate-600'}`}>{compLabel(key)}</span>
                    <span className="h-1.5 rounded-full bg-slate-100">
                      <span className="block h-full rounded-full" style={{ width: `${v}%`, background: color(gr.id) }} />
                    </span>
                    <span className="text-right tabular-nums text-slate-600">{v.toFixed(0)}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-slate-500">{gr.description}</p>
              <button className="mt-2 text-xs font-medium text-slate-700 hover:underline" onClick={() => setOpen(open === gr.id ? null : gr.id)}>
                {open === gr.id ? 'Hide members' : `Show ${members.length} members`}
              </button>
              {open === gr.id && (
                <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto text-sm">
                  {members.map((m) => (
                    <li key={m.learner.id} className="flex items-center gap-2">
                      <Link to={`/app/educator/learners/${m.learner.id}`} className="hover:underline">
                        {m.learner.name}
                      </Link>
                      {m.learner.synthetic && <DemoBadge />}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )
        })}
      </div>

      <div className="grid gap-6 xl:grid-cols-5">
        <Card title="Group map (PCA)" className="xl:col-span-3">
          <GroupScatter g={g} />
        </Card>
        <Card title="Choosing the number of groups" className="xl:col-span-2">
          <ModelSelection g={g} />
        </Card>
      </div>

      <Card title={`Movement between groups · ${g.period_dates.map(monthLabel).join(' → ')}`}>
        <Transitions g={g} />
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Algorithm comparison (current period)">
          <Algorithms g={g} />
        </Card>
        {g.persona_agreement && (
          <Card title="Agreement with demo personas">
            <PersonaAgreement g={g} />
          </Card>
        )}
      </div>
      <p className="text-xs text-slate-500">
        Features: {g.features}. K-Means is fitted on all three periods together so each group means the same thing over time.
      </p>
    </>
  )
}

function Legend({ g }: { g: Grouping }) {
  return (
    <div className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
      {g.groups.map((gr) => (
        <span key={gr.id} className="inline-flex items-center gap-1.5">
          <span style={{ color: color(gr.id) }} aria-hidden>
            {GLYPH[gr.id]}
          </span>
          {gr.name}
        </span>
      ))}
    </div>
  )
}

function GroupScatter({ g }: { g: Grouping }) {
  const now = g.period_dates.length - 1
  const byGroup = g.groups.map((gr) =>
    g.members
      .filter((m) => m.position && m.states[now] === gr.id)
      .map((m) => ({ x: m.position![0], y: m.position![1], name: m.learner.name, group: gr.name })),
  )
  return (
    <div>
      <Legend g={g} />
      <div className="h-80" role="img" aria-label={`Scatter plot of ${g.members.length} learners on two principal components, marked by group`}>
        <ResponsiveContainer>
          <ScatterChart margin={{ top: 8, right: 12, bottom: 16, left: -8 }}>
            <CartesianGrid stroke={GRID} />
            <XAxis type="number" dataKey="x" tick={AXIS} tickLine={false} name="PC1" label={{ value: `PC1 (${Math.round(100 * g.pca_explained[0])}% of variance)`, position: 'insideBottom', offset: -8, fill: '#64748b', fontSize: 11 }} />
            <YAxis type="number" dataKey="y" tick={AXIS} tickLine={false} name="PC2" label={{ value: `PC2 (${Math.round(100 * g.pca_explained[1])}%)`, angle: -90, position: 'insideLeft', offset: 20, fill: '#64748b', fontSize: 11 }} />
            <Tooltip
              cursor={{ strokeDasharray: '3 3' }}
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-sm">
                    <div className="font-semibold text-slate-900">{String(payload[0].payload.name)}</div>
                    <div className="text-slate-500">{String(payload[0].payload.group)}</div>
                  </div>
                ) : null
              }
            />
            {byGroup.map((pts, i) => (
              <Scatter key={i} data={pts} fill={color(i)} shape={SHAPES[i]} fillOpacity={0.8} isAnimationActive={false} />
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <p className="text-xs text-slate-500">Nearby learners have similar profiles. The axes are combinations of the features, not single competencies.</p>
    </div>
  )
}

function MiniLine({ data, dataKey, label, k }: { data: Grouping['k_selection']; dataKey: 'silhouette' | 'davies_bouldin' | 'inertia'; label: string; k: number }) {
  return (
    <div>
      <div className="text-xs font-medium text-slate-600">{label}</div>
      <div className="h-24">
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -20 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="k" tick={AXIS} tickLine={false} />
            <YAxis tick={AXIS} tickLine={false} axisLine={false} width={48} tickFormatter={(v: number) => (dataKey === 'inertia' ? v.toFixed(0) : v.toFixed(2))} domain={['auto', 'auto']} />
            <ReferenceLine x={k} stroke="#0f172a" strokeDasharray="3 3" />
            <Tooltip formatter={(v) => [Number(v).toFixed(3), label]} labelFormatter={(l) => `k = ${l}`} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            <Line dataKey={dataKey} stroke={SERIES_COLORS[0]} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function ModelSelection({ g }: { g: Grouping }) {
  return (
    <div className="space-y-3">
      <MiniLine data={g.k_selection} dataKey="silhouette" label="Silhouette (higher is better)" k={g.k} />
      <MiniLine data={g.k_selection} dataKey="davies_bouldin" label="Davies–Bouldin index (lower is better)" k={g.k} />
      <MiniLine data={g.k_selection} dataKey="inertia" label="Inertia (look for the elbow)" k={g.k} />
      <p className="text-xs text-slate-500">Dashed line: the k in use.</p>
    </div>
  )
}

type SNode = { name: string; group: number; period: number }

function Transitions({ g }: { g: Grouping }) {
  const names = (s: number) => (s < 0 ? 'Not active yet' : g.groups[s]?.name ?? `Group ${s}`)
  // Nodes per (period, state) that carry any learners
  const nodes: SNode[] = []
  const index = new Map<string, number>()
  const node = (period: number, state: number) => {
    const key = `${period}:${state}`
    if (!index.has(key)) {
      index.set(key, nodes.length)
      nodes.push({ name: names(state), group: state, period })
    }
    return index.get(key)!
  }
  const links = g.transitions.flatMap((pairs, p) =>
    pairs.filter((t) => t.learners > 0).map((t) => ({ source: node(p, t.source), target: node(p + 1, t.target), value: t.learners })),
  )
  const last = g.transitions[g.transitions.length - 1] ?? []
  const states = [...new Set(last.flatMap((t) => [t.source, t.target]))].sort((a, b) => a - b)
  const cell = (a: number, b: number) => last.find((t) => t.source === a && t.target === b)?.learners ?? 0

  const SankeyNodeShape = ({ x, y, width, height, payload }: NodeProps) => {
    const n = payload as unknown as SNode
    const right = n.period === g.period_dates.length - 1
    return (
      <g>
        <rect x={x} y={y} width={width} height={height} fill={color(n.group)} rx={2} />
        {height > 10 && (
          <text x={right ? x - 6 : x + width + 6} y={y + height / 2} dy={4} textAnchor={right ? 'end' : 'start'} fontSize={11} fill="#334155">
            {n.name.length > 30 ? `${n.name.slice(0, 29)}…` : n.name}
          </text>
        )}
      </g>
    )
  }
  const SankeyLinkShape = ({ sourceX, targetX, sourceY, targetY, sourceControlX, targetControlX, linkWidth, payload }: LinkProps) => (
    <path
      d={`M${sourceX},${sourceY} C${sourceControlX},${sourceY} ${targetControlX},${targetY} ${targetX},${targetY}`}
      fill="none"
      stroke={color((payload.source as unknown as SNode).group)}
      strokeOpacity={0.3}
      strokeWidth={Math.max(1, linkWidth)}
    />
  )

  return (
    <div className="space-y-5">
      <div className="flex justify-between text-xs font-medium text-slate-500">
        {g.period_dates.map((d) => (
          <span key={d}>{monthLabel(d)}</span>
        ))}
      </div>
      <div className="h-80" role="img" aria-label="Sankey diagram of learners moving between groups across three periods">
        <ResponsiveContainer>
          <Sankey data={{ nodes, links }} node={SankeyNodeShape} link={SankeyLinkShape} nodePadding={14} nodeWidth={10} margin={{ top: 4, bottom: 4, left: 4, right: 4 }}>
            <Tooltip
              content={({ active, payload }) => {
                const p = payload?.[0]?.payload as { payload?: { source?: SNode; target?: SNode; value?: number; name?: string } } | undefined
                const d = p?.payload
                if (!active || !d) return null
                return (
                  <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-sm">
                    {d.source && d.target ? (
                      <>
                        <span className="font-semibold tabular-nums">{d.value}</span> learners: {d.source.name} → {d.target.name}
                      </>
                    ) : (
                      d.name
                    )}
                  </div>
                )
              }}
            />
          </Sankey>
        </ResponsiveContainer>
      </div>
      <div className="overflow-x-auto">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
          Transition matrix · {monthLabel(g.period_dates[g.period_dates.length - 2])} (rows) → {monthLabel(g.period_dates[g.period_dates.length - 1])} (columns)
        </h3>
        <table className="text-xs">
          <thead>
            <tr>
              <th />
              {states.map((s) => (
                <th key={s} className="px-2 pb-1 text-center font-medium text-slate-600" title={names(s)}>
                  <span style={{ color: color(s) }}>{s < 0 ? '–' : GLYPH[s]}</span>
                </th>
              ))}
              <th className="px-2 pb-1 text-right font-medium text-slate-500">Stayed</th>
            </tr>
          </thead>
          <tbody>
            {states.map((a) => {
              const total = states.reduce((n, b) => n + cell(a, b), 0)
              return (
                <tr key={a}>
                  <th className="max-w-64 truncate py-1 pr-3 text-left font-medium text-slate-700" title={names(a)}>
                    <span style={{ color: color(a) }}>{a < 0 ? '–' : GLYPH[a]}</span> {names(a)}
                  </th>
                  {states.map((b) => (
                    <td key={b} className={`px-2 py-1 text-center tabular-nums ${a === b ? 'bg-slate-100 font-semibold' : 'text-slate-600'}`}>
                      {cell(a, b) || '·'}
                    </td>
                  ))}
                  <td className="px-2 py-1 text-right tabular-nums text-slate-600">{total ? `${Math.round((100 * cell(a, a)) / total)}%` : '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Algorithms({ g }: { g: Grouping }) {
  const truth = g.algorithms.some((a) => a.ari != null)
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-xs text-slate-500">
          <tr>
            <th className="pb-2 font-medium">Algorithm</th>
            <th className="pb-2 text-right font-medium">Groups</th>
            <th className="pb-2 text-right font-medium">Unassigned</th>
            <th className="pb-2 text-right font-medium" title="Higher is better">Silhouette</th>
            <th className="pb-2 text-right font-medium" title="Lower is better">Davies–Bouldin</th>
            {truth && <th className="pb-2 text-right font-medium" title="Agreement with demo personas">ARI</th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {g.algorithms.map((a) => (
            <tr key={a.name}>
              <td className="py-2 pr-2">{a.name}</td>
              <td className="py-2 text-right tabular-nums">{a.n_clusters}</td>
              <td className="py-2 text-right tabular-nums">{a.noise ? `${Math.round(100 * a.noise)}%` : '—'}</td>
              <td className="py-2 text-right tabular-nums">{f2(a.silhouette)}</td>
              <td className="py-2 text-right tabular-nums">{f2(a.davies_bouldin)}</td>
              {truth && <td className="py-2 text-right tabular-nums">{f2(a.ari)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 text-xs text-slate-500">
        The app uses K-Means because it can place learners' <em>past</em> profiles into the same groups, which the movement view needs. DBSCAN leaves
        outliers unassigned.
      </p>
    </div>
  )
}

const PERSONA = { coder: 'Coder', leader: 'Leader', researcher: 'Researcher', all_rounder: 'All-rounder', fading: 'Fading' } as Record<string, string>

function PersonaAgreement({ g }: { g: Grouping }) {
  const a = g.persona_agreement!
  return (
    <div>
      <p className="text-sm text-slate-600">
        Adjusted Rand Index <span className="font-semibold tabular-nums">{a.ari.toFixed(2)}</span> · NMI{' '}
        <span className="font-semibold tabular-nums">{a.nmi.toFixed(2)}</span> (1 = groups match personas exactly, 0 = chance).
      </p>
      <table className="mt-3 w-full text-xs">
        <thead className="text-left text-slate-500">
          <tr>
            <th className="pb-1 font-medium">Persona</th>
            <th className="pb-1 font-medium">Groups (learners)</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {Object.entries(a.contingency).map(([p, groups]) => (
            <tr key={p} className="align-top">
              <td className="py-1.5 pr-3 font-medium">{PERSONA[p] ?? p}</td>
              <td className="py-1.5 text-slate-600">
                {Object.entries(groups)
                  .sort((x, y) => y[1] - x[1])
                  .map(([name, n]) => `${name} (${n})`)
                  .join(' · ')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 text-xs text-slate-500">
        Coders and fading learners usually share a group: they focus on the same competencies and differ in direction, which the trend labels show.
      </p>
    </div>
  )
}
