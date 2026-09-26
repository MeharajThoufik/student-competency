import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useAuth } from '../../auth/AuthProvider'
import { Alert, Button, Card, Empty, Field, Input, Select, Spinner, titleCase } from '../../components/ui'
import { api, type Role, type ScoringConfig, type Weights } from '../../lib/api'

const TABS = [
  { key: 'users', label: 'Users & roles' },
  { key: 'weights', label: 'Scoring weights' },
  { key: 'demo', label: 'Demo data' },
  { key: 'audit', label: 'Audit log' },
] as const
type Tab = (typeof TABS)[number]['key']

export function Admin() {
  const [tab, setTab] = useState<Tab>('users')
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Administration</h1>
      <div className="inline-flex flex-wrap rounded-lg bg-slate-100 p-1" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium ${tab === t.key ? 'bg-white shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'users' && <UsersTab />}
      {tab === 'weights' && <WeightsTab />}
      {tab === 'demo' && <DemoTab />}
      {tab === 'audit' && <AuditTab />}
    </div>
  )
}

// ---------- Users ----------
function UsersTab() {
  const { user: me } = useAuth()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [q, setQ] = useState('')
  useEffect(() => {
    const t = setTimeout(() => setQ(search.trim()), 300)
    return () => clearTimeout(t)
  }, [search])
  const users = useQuery({ queryKey: ['admin-users', q], queryFn: () => api.adminUsers(q) })
  const setRole = useMutation({
    mutationFn: (v: { id: number; role: Role }) => api.setRole(v.id, v.role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      queryClient.invalidateQueries({ queryKey: ['learners'] })
    },
  })

  return (
    <Card title="Users and roles" action={<span className="text-xs text-slate-500">Changes take effect on the user's next request</span>}>
      <div className="relative mb-4 max-w-sm">
        <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-slate-400" />
        <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name, email or register no." className="pl-9" />
      </div>
      {setRole.error && (
        <div className="mb-3">
          <Alert>{setRole.error.message}</Alert>
        </div>
      )}
      {users.isPending ? (
        <Spinner />
      ) : users.error ? (
        <Alert>{users.error.message}</Alert>
      ) : !users.data.length ? (
        <Empty>No users found.</Empty>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-slate-500">
              <tr>
                <th className="pb-2 font-medium">Name</th>
                <th className="pb-2 font-medium">Email</th>
                <th className="pb-2 font-medium">Last sign-in</th>
                <th className="pb-2 font-medium">Role</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {users.data.map((u) => (
                <tr key={u.id}>
                  <td className="py-2 pr-3">
                    <div className="font-medium">{u.name}</div>
                    {u.register_no && <div className="text-xs text-slate-500">{u.register_no}</div>}
                  </td>
                  <td className="py-2 pr-3 text-slate-600">{u.email}</td>
                  <td className="py-2 pr-3 tabular-nums text-slate-600">{u.last_login_at?.slice(0, 10) ?? '—'}</td>
                  <td className="py-2">
                    <Select
                      value={u.role}
                      disabled={u.id === me?.id || setRole.isPending}
                      title={u.id === me?.id ? 'You cannot change your own role' : undefined}
                      onChange={(e) => {
                        const role = e.target.value as Role
                        if (confirm(`Change ${u.name}'s role from ${u.role} to ${role}?`)) setRole.mutate({ id: u.id, role })
                      }}
                      className="w-32 py-1"
                      aria-label={`Role of ${u.name}`}
                    >
                      <option value="learner">Learner</option>
                      <option value="educator">Educator</option>
                      <option value="admin">Admin</option>
                    </Select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

// ---------- Weights ----------
// Sequential blue ramp (dataviz reference): heavier weight → darker cell.
const RAMP = ['#ffffff', '#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf']
const cellColor = (w: number) => RAMP[Math.min(RAMP.length - 1, Math.ceil(w * (RAMP.length - 1)))]

function WeightsTab() {
  const config = useQuery({ queryKey: ['scoring-config'], queryFn: api.scoringConfig, staleTime: Infinity })
  if (config.isPending) return <Spinner />
  if (config.error) return <Alert>{config.error.message}</Alert>
  return <WeightEditor key={JSON.stringify(config.data.weights)} config={config.data} />
}

function WeightEditor({ config }: { config: ScoringConfig }) {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<Weights>(() => structuredClone(config.weights))
  const comps = config.competencies
  const types = Object.keys(config.activity_types)
  const original = (t: string, c: string) => config.weights[t]?.[c] ?? 0
  const value = (t: string, c: string) => draft[t]?.[c] ?? 0

  const changes: Weights = {}
  for (const t of types)
    for (const c of comps)
      if (value(t, c.key) !== original(t, c.key)) (changes[t] ??= {})[c.key] = value(t, c.key)
  const changeCount = Object.values(changes).reduce((n, r) => n + Object.keys(r).length, 0)

  const refresh = () => {
    for (const key of ['scoring-config', 'competencies', 'insights', 'learners', 'learner', 'cohort']) queryClient.invalidateQueries({ queryKey: [key] })
  }
  const save = useMutation({ mutationFn: () => api.updateWeights(changes), onSuccess: refresh })
  const reset = useMutation({ mutationFn: api.resetWeights, onSuccess: refresh })

  const set = (t: string, c: string, raw: string) => {
    const w = Math.min(1, Math.max(0, Number(raw) || 0))
    setDraft({ ...draft, [t]: { ...draft[t], [c]: Math.round(w * 100) / 100 } })
  }

  return (
    <Card title="Activity type → competency weights">
      <p className="mb-4 text-sm text-slate-600">
        How strongly each activity type develops each competency (0 to 1). Scores are calculated when viewed, so a change here updates every learner's
        scores immediately. Snapshots already recorded are kept as they were. Every change is written to the audit log.
      </p>
      <div className="overflow-x-auto">
        <table className="text-sm">
          <thead>
            <tr>
              <th />
              {comps.map((c) => (
                <th key={c.key} className="px-1 pb-2 text-center text-xs font-medium text-slate-600" style={{ minWidth: 72 }}>
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {types.map((t) => (
              <tr key={t}>
                <th className="whitespace-nowrap py-0.5 pr-3 text-left text-xs font-medium text-slate-700">{config.activity_types[t]}</th>
                {comps.map((c) => {
                  const w = value(t, c.key)
                  const changed = w !== original(t, c.key)
                  return (
                    <td key={c.key} className="p-0.5">
                      <input
                        type="number"
                        min={0}
                        max={1}
                        step={0.1}
                        value={w}
                        onChange={(e) => set(t, c.key, e.target.value)}
                        aria-label={`${config.activity_types[t]} → ${c.label}`}
                        title={changed ? `Was ${original(t, c.key)}` : undefined}
                        className={`w-full rounded px-1.5 py-1 text-center tabular-nums outline-none focus:ring-2 focus:ring-slate-900 ${
                          changed ? 'ring-2 ring-amber-500' : ''
                        } ${w > 0.55 ? 'text-white' : 'text-slate-900'}`}
                        style={{ background: cellColor(w) }}
                      />
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {(save.error || reset.error) && (
        <div className="mt-3">
          <Alert>{(save.error ?? reset.error)!.message}</Alert>
        </div>
      )}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button disabled={!changeCount} loading={save.isPending} onClick={() => save.mutate()}>
          Save {changeCount ? `${changeCount} change${changeCount > 1 ? 's' : ''}` : 'changes'}
        </Button>
        <Button variant="secondary" disabled={!changeCount} onClick={() => setDraft(structuredClone(config.weights))}>
          Discard
        </Button>
        <span className="flex-1" />
        <Button
          variant="ghost"
          loading={reset.isPending}
          onClick={() => {
            if (confirm('Reset all weights to the original expert-defined values?')) reset.mutate()
          }}
        >
          Reset to defaults
        </Button>
      </div>
    </Card>
  )
}

// ---------- Demo data ----------
function DemoTab() {
  const queryClient = useQueryClient()
  const summary = useQuery({ queryKey: ['synthetic'], queryFn: api.syntheticSummary })
  const [learners, setLearners] = useState(200)
  const [seed, setSeed] = useState(42)
  const refresh = () => {
    for (const key of ['synthetic', 'learners', 'cohort', 'review-queue', 'insights']) queryClient.invalidateQueries({ queryKey: [key] })
  }
  const generate = useMutation({ mutationFn: () => api.generateSynthetic(learners, seed), onSuccess: refresh })
  const clear = useMutation({ mutationFn: api.clearSynthetic, onSuccess: refresh })

  return (
    <Card title="Demo (synthetic) learners">
      <p className="text-sm text-slate-600">
        Generated learners with known growth patterns (coder, leader, researcher, all-rounder, fading). They are used for demonstrations and for evaluating
        the trend detection. They cannot sign in and are hidden from educator lists unless "demo learners" is selected.
      </p>
      <div className="mt-4">
        {summary.isPending ? (
          <Spinner />
        ) : summary.data?.total ? (
          <div className="flex flex-wrap gap-2 text-sm">
            <span className="font-semibold">{summary.data.total} demo learners:</span>
            {Object.entries(summary.data.by_persona).map(([p, n]) => (
              <span key={p} className="rounded bg-slate-100 px-2 py-0.5">
                {titleCase(p)} {n}
              </span>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500">No demo learners.</p>
        )}
      </div>
      <div className="mt-5 flex flex-wrap items-end gap-3">
        <Field label="Learners">
          <Input type="number" min={1} max={1000} value={learners} onChange={(e) => setLearners(+e.target.value)} className="w-28" />
        </Field>
        <Field label="Random seed">
          <Input type="number" value={seed} onChange={(e) => setSeed(+e.target.value)} className="w-28" />
        </Field>
        <Button
          loading={generate.isPending}
          onClick={() => {
            if (confirm(`Replace all demo learners with ${learners} new ones (seed ${seed})?`)) generate.mutate()
          }}
        >
          Generate
        </Button>
        <Button
          variant="danger"
          disabled={!summary.data?.total}
          loading={clear.isPending}
          onClick={() => {
            if (confirm('Delete all demo learners?')) clear.mutate()
          }}
        >
          Delete all
        </Button>
      </div>
      <p className="mt-2 text-xs text-slate-500">Generating 200 learners takes about 30 seconds. The same seed always produces the same learners.</p>
      {(generate.error || clear.error) && (
        <div className="mt-3">
          <Alert>{(generate.error ?? clear.error)!.message}</Alert>
        </div>
      )}
    </Card>
  )
}

// ---------- Audit ----------
const ACTION_LABELS: Record<string, string> = {
  activity_verified: 'Verified activity',
  activity_rejected: 'Rejected activity',
  role_changed: 'Changed role',
  weights_updated: 'Updated weights',
  weights_reset: 'Reset weights',
  synthetic_generated: 'Generated demo data',
  synthetic_deleted: 'Deleted demo data',
}

function describe(action: string, d: Record<string, unknown>): string {
  if (action === 'role_changed') return `${d.email}: ${d.previous} → ${d.new}`
  if (action.startsWith('activity_')) return d.note ? `Note: ${d.note}` : ''
  if (action.startsWith('weights_') && d.changes) {
    const parts = Object.entries(d.changes as Record<string, Record<string, [number, number]>>).flatMap(([t, cs]) =>
      Object.entries(cs).map(([c, [a, b]]) => `${t}/${c} ${a}→${b}`),
    )
    return parts.slice(0, 6).join(', ') + (parts.length > 6 ? ` +${parts.length - 6} more` : '')
  }
  if (action === 'synthetic_generated') return `${d.learners} learners, seed ${d.seed}`
  if (action === 'synthetic_deleted') return `${d.deleted} learners`
  return ''
}

function AuditTab() {
  const log = useQuery({ queryKey: ['audit'], queryFn: api.audit })
  if (log.isPending) return <Spinner />
  if (log.error) return <Alert>{log.error.message}</Alert>
  return (
    <Card title="Audit log" action={<span className="text-xs text-slate-500">Latest 200 privileged actions</span>}>
      {!log.data.length ? (
        <Empty>No actions recorded yet.</Empty>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-slate-500">
              <tr>
                <th className="pb-2 font-medium">When</th>
                <th className="pb-2 font-medium">Who</th>
                <th className="pb-2 font-medium">Action</th>
                <th className="pb-2 font-medium">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {log.data.map((a) => (
                <tr key={a.id} className="align-top">
                  <td className="whitespace-nowrap py-2 pr-3 tabular-nums text-slate-600">{a.created_at.slice(0, 16).replace('T', ' ')}</td>
                  <td className="py-2 pr-3 text-slate-600">{a.actor ?? '—'}</td>
                  <td className="whitespace-nowrap py-2 pr-3 font-medium">
                    {ACTION_LABELS[a.action] ?? titleCase(a.action)}
                    {a.target_id != null && <span className="font-normal text-slate-500"> #{a.target_id}</span>}
                  </td>
                  <td className="py-2 text-slate-600">{describe(a.action, a.details)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
