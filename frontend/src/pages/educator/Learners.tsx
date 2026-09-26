import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { DemoBadge, RISK_LABELS, RiskBadges, SyntheticSelect } from '../../components/educator'
import { Alert, Button, Empty, Input, Select, Spinner } from '../../components/ui'
import { api, type Synthetic } from '../../lib/api'

const PAGE = 50
const SORTS = {
  name: 'Name',
  mean_score: 'Average score',
  activity_count: 'Most activities',
  last_activity: 'Recently active',
  pending_reviews: 'Pending reviews',
}

export function Learners() {
  const [search, setSearch] = useState('')
  const [q, setQ] = useState('')
  const [synthetic, setSynthetic] = useState<Synthetic>('exclude')
  const [atRisk, setAtRisk] = useState(false)
  const [sort, setSort] = useState<keyof typeof SORTS>('name')
  const [offset, setOffset] = useState(0)

  useEffect(() => {
    const t = setTimeout(() => {
      setQ(search.trim())
      setOffset(0)
    }, 300)
    return () => clearTimeout(t)
  }, [search])

  const params = { q, synthetic, at_risk: String(atRisk), sort, limit: String(PAGE), offset: String(offset) }
  const list = useQuery({ queryKey: ['learners', params], queryFn: () => api.learners(params), placeholderData: keepPreviousData })
  const config = useQuery({ queryKey: ['scoring-config'], queryFn: api.scoringConfig, staleTime: Infinity })
  const label = (k: string | null) => (k ? (config.data?.competencies.find((c) => c.key === k)?.label ?? k) : '—')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Learners</h1>
        <p className="text-sm text-slate-500">Scores and risk flags are calculated live from each learner's activities.</p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-56 flex-1">
          <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-slate-400" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name, email or register no." className="pl-9" />
        </div>
        <SyntheticSelect value={synthetic} onChange={(v) => { setSynthetic(v); setOffset(0) }} />
        <Select value={sort} onChange={(e) => setSort(e.target.value as keyof typeof SORTS)} className="w-auto" aria-label="Sort">
          {Object.entries(SORTS).map(([k, v]) => (
            <option key={k} value={k}>
              Sort: {v}
            </option>
          ))}
        </Select>
        <label className="inline-flex items-center gap-2 text-sm">
          <input type="checkbox" checked={atRisk} onChange={(e) => { setAtRisk(e.target.checked); setOffset(0) }} /> At risk only
        </label>
      </div>

      {list.isPending ? (
        <Spinner />
      ) : list.error ? (
        <Alert>{list.error.message}</Alert>
      ) : !list.data.items.length ? (
        <Empty>No learners match. Learners appear here after they sign up and give consent.</Empty>
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="w-full text-sm">
              <thead className="border-b border-slate-100 text-left text-xs text-slate-500">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Learner</th>
                  <th className="px-3 py-2.5 text-right font-medium">Activities</th>
                  <th className="px-3 py-2.5 font-medium">Last active</th>
                  <th className="px-3 py-2.5 text-right font-medium">Avg score</th>
                  <th className="px-3 py-2.5 font-medium">Strongest</th>
                  <th className="px-3 py-2.5 text-right font-medium">To review</th>
                  <th className="px-3 py-2.5 font-medium">Flags</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {list.data.items.map((r) => (
                  <tr key={r.learner.id} className="hover:bg-slate-50">
                    <td className="px-4 py-2.5">
                      <Link to={`/app/educator/learners/${r.learner.id}`} className="font-medium hover:underline">
                        {r.learner.name}
                      </Link>{' '}
                      {r.learner.synthetic && <DemoBadge />}
                      <div className="text-xs text-slate-500">{[r.learner.register_no, r.learner.batch].filter(Boolean).join(' · ') || r.learner.email}</div>
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{r.activity_count}</td>
                    <td className="px-3 py-2.5 tabular-nums text-slate-600">{r.last_activity ?? '—'}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{r.mean_score.toFixed(1)}</td>
                    <td className="px-3 py-2.5 text-slate-600">{label(r.top_competency)}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{r.pending_reviews || '—'}</td>
                    <td className="px-3 py-2.5">
                      <RiskBadges risks={r.risks} rules={list.data.risk_rules} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between text-sm text-slate-600">
            <span>
              {offset + 1}–{Math.min(offset + PAGE, list.data.total)} of {list.data.total}
            </span>
            <span className="flex gap-2">
              <Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
                Previous
              </Button>
              <Button variant="secondary" disabled={offset + PAGE >= list.data.total} onClick={() => setOffset(offset + PAGE)}>
                Next
              </Button>
            </span>
          </div>
          <dl className="grid gap-1 text-xs text-slate-500 sm:grid-cols-3">
            {Object.entries(list.data.risk_rules).map(([k, v]) => (
              <div key={k}>
                <dt className="inline font-medium text-slate-700">{RISK_LABELS[k] ?? k}:</dt>{' '}
                <dd className="inline">{v}</dd>
              </div>
            ))}
          </dl>
        </>
      )}
    </div>
  )
}
