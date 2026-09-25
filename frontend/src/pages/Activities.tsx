import { useQuery } from '@tanstack/react-query'
import { Paperclip, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge, Empty, EvidenceBadge, Select, Spinner, titleCase } from '../components/ui'
import { api } from '../lib/api'

export function Activities() {
  const activities = useQuery({ queryKey: ['activities'], queryFn: api.activities })
  const [type, setType] = useState('all')

  const list = (activities.data ?? []).filter((a) => type === 'all' || a.type.key === type)
  const types = [...new Map((activities.data ?? []).map((a) => [a.type.key, a.type.label]))]

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Activities</h1>
          <p className="text-sm text-slate-500">Projects, certifications, events and achievements that build your competencies.</p>
        </div>
        <Link
          to="/app/activities/new"
          className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-3.5 py-2 text-sm font-medium text-white hover:bg-slate-700"
        >
          <Plus className="size-4" /> Add activity
        </Link>
      </div>

      {types.length > 1 && (
        <Select value={type} onChange={(e) => setType(e.target.value)} className="w-auto">
          <option value="all">All types</option>
          {types.map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </Select>
      )}

      {activities.isPending ? (
        <Spinner />
      ) : !list.length ? (
        <Empty>No activities yet. Add a project, certification, hackathon or club role to get started.</Empty>
      ) : (
        <ul className="space-y-3">
          {list.map((a) => (
            <li key={a.id}>
              <Link to={`/app/activities/${a.id}`} className="block rounded-xl border border-slate-200 bg-white p-4 hover:border-slate-300">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="font-medium">{a.title}</div>
                    <div className="mt-0.5 text-sm text-slate-500">
                      {a.type.label}
                      {a.organization && ` · ${a.organization}`} · {a.start_date}
                      {a.end_date && ` → ${a.end_date}`}
                    </div>
                  </div>
                  <EvidenceBadge status={a.evidence_status} />
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-1.5">
                  <Badge>{titleCase(a.outcome)}</Badge>
                  <Badge>{titleCase(a.scope)}</Badge>
                  {a.skills.map((s) => (
                    <Badge key={s} tone="blue">
                      {s}
                    </Badge>
                  ))}
                  {a.evidence.length > 0 && (
                    <span className="ml-auto inline-flex items-center gap-1 text-xs text-slate-500">
                      <Paperclip className="size-3.5" /> {a.evidence.length}
                    </span>
                  )}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
