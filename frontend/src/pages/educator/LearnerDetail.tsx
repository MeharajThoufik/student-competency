import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ActivitySummary, DemoBadge, EvidenceLinks, ReviewActions, RiskBadges } from '../../components/educator'
import { Alert, Card, Empty, Level, Spinner } from '../../components/ui'
import { api, type LearnerDetail as Detail } from '../../lib/api'
import { GrowthView } from '../Growth'

export function LearnerDetail() {
  const { id } = useParams()
  const detail = useQuery({ queryKey: ['learner', id], queryFn: () => api.learner(+id!) })

  if (detail.isPending) return <Spinner />
  if (detail.error) return <Alert>{detail.error.message}</Alert>
  const d = detail.data
  const p = d.profile
  const pending = d.activities.filter((a) => a.verification_status === 'unverified' && a.evidence.length)

  return (
    <div className="space-y-6">
      <Link to="/app/educator/learners" className="inline-flex items-center gap-1 text-sm text-slate-600 hover:underline">
        <ArrowLeft className="size-4" /> Learners
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold">
            {p.name} {p.synthetic && <DemoBadge />}
          </h1>
          <p className="text-sm text-slate-500">
            {[p.register_no, p.programme, p.batch, p.email].filter(Boolean).join(' · ')}
          </p>
          <div className="mt-2">
            <RiskBadges risks={d.risks} rules={d.risk_rules} />
          </div>
        </div>
        <div className="flex gap-6 text-right">
          <Stat label="CGPA" value={d.academics.cgpa?.toFixed(2) ?? '—'} />
          <Stat label="Activities" value={d.activities.length} />
          <Stat label="To review" value={pending.length} />
        </div>
      </div>

      {d.risks.length > 0 && (
        <ul className="space-y-1 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {d.risks.map((r) => (
            <li key={r}>{d.risk_rules[r]}</li>
          ))}
        </ul>
      )}

      {(p.career_goals || p.bio) && (
        <Card title="About">
          {p.career_goals && (
            <p className="text-sm">
              <span className="font-medium">Career goals:</span> {p.career_goals}
            </p>
          )}
          {p.bio && <p className="mt-2 text-sm text-slate-600">{p.bio}</p>}
        </Card>
      )}

      {pending.length > 0 && (
        <Card title={`Waiting for review (${pending.length})`}>
          <ul className="divide-y divide-slate-100">
            {pending.map((a) => (
              <li key={a.id} className="space-y-3 py-4 first:pt-0 last:pb-0">
                <ActivitySummary activity={a}>
                  <EvidenceLinks activity={a} />
                </ActivitySummary>
                <ReviewActions activity={a} />
              </li>
            ))}
          </ul>
        </Card>
      )}

      <GrowthView data={d.insights} readOnly />

      <AllActivities detail={d} />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Academics">
          {!d.academics.semesters.length ? (
            <Empty>No course results recorded.</Empty>
          ) : (
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-slate-500">
                <tr>
                  <th className="pb-2 font-medium">Semester</th>
                  <th className="pb-2 text-right font-medium">Credits</th>
                  <th className="pb-2 text-right font-medium">SGPA</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {d.academics.semesters.map((s) => (
                  <tr key={s.semester}>
                    <td className="py-1.5">{s.semester}</td>
                    <td className="py-1.5 text-right tabular-nums">{s.credits}</td>
                    <td className="py-1.5 text-right tabular-nums">{s.sgpa.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="font-semibold">
                  <td className="pt-2">CGPA</td>
                  <td className="pt-2 text-right tabular-nums">{d.academics.total_credits}</td>
                  <td className="pt-2 text-right tabular-nums">{d.academics.cgpa?.toFixed(2)}</td>
                </tr>
              </tfoot>
            </table>
          )}
        </Card>
        <Card title="Self-rated skills">
          {!d.skills.length ? (
            <Empty>No skills recorded.</Empty>
          ) : (
            <ul className="grid gap-2 sm:grid-cols-2">
              {d.skills.map((s) => (
                <li key={s.id} className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-1.5 text-sm">
                  {s.name} <Level value={s.self_level} />
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <div className="text-xl font-semibold tabular-nums">{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  )
}

function AllActivities({ detail }: { detail: Detail }) {
  const [open, setOpen] = useState<number | null>(null)
  if (!detail.activities.length) return null
  return (
    <Card title={`All activities (${detail.activities.length})`}>
      <ul className="divide-y divide-slate-100">
        {detail.activities.map((a) => (
          <li key={a.id} className="py-3 first:pt-0 last:pb-0">
            <button className="w-full text-left" onClick={() => setOpen(open === a.id ? null : a.id)} aria-expanded={open === a.id}>
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="text-sm font-medium">{a.title}</span>
                <span className="text-xs text-slate-500">
                  {a.type.label} · {a.start_date}
                </span>
              </div>
            </button>
            {open === a.id ? (
              <div className="mt-3 space-y-3">
                <ActivitySummary activity={a}>
                  <EvidenceLinks activity={a} />
                </ActivitySummary>
                <ReviewActions activity={a} />
              </div>
            ) : (
              <div className="mt-1 text-xs text-slate-500">
                {a.verification_status === 'rejected' ? 'Rejected' : a.evidence_status.replace('_', ' ')}
              </div>
            )}
          </li>
        ))}
      </ul>
    </Card>
  )
}
