import { useQuery } from '@tanstack/react-query'
import { Award, GraduationCap, Plus, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { CompetencyProfile } from '../components/CompetencyProfile'
import { Card, EvidenceBadge } from '../components/ui'
import { api } from '../lib/api'

function Stat({ label, value, icon: Icon, to }: { label: string; value: string | number; icon: typeof Award; to: string }) {
  return (
    <Link to={to} className="rounded-xl border border-slate-200 bg-white p-5 hover:border-slate-300">
      <Icon className="size-5 text-slate-400" />
      <div className="mt-3 text-2xl font-semibold">{value}</div>
      <div className="text-sm text-slate-500">{label}</div>
    </Link>
  )
}

export function Dashboard() {
  const { user } = useAuth()
  const activities = useQuery({ queryKey: ['activities'], queryFn: api.activities })
  const summary = useQuery({ queryKey: ['academic-summary'], queryFn: api.academicSummary })
  const skills = useQuery({ queryKey: ['skills'], queryFn: api.skills })

  const acts = activities.data ?? []
  const withEvidence = acts.filter((a) => a.evidence_status !== 'self_reported').length
  const profileFields = [user?.register_no, user?.programme, user?.department, user?.batch, user?.career_goals]
  const completeness = Math.round(
    ((profileFields.filter(Boolean).length + (acts.length ? 1 : 0) + (skills.data?.length ? 1 : 0) + (summary.data?.cgpa != null ? 1 : 0)) /
      (profileFields.length + 3)) *
      100,
  )

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Welcome, {user?.name}</h1>
          <p className="text-sm text-slate-500">Profile {completeness}% complete</p>
        </div>
        <Link
          to="/app/activities/new"
          className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-3.5 py-2 text-sm font-medium text-white hover:bg-slate-700"
        >
          <Plus className="size-4" /> Add activity
        </Link>
      </div>

      <div className="h-2 overflow-hidden rounded-full bg-slate-200">
        <div className="h-full rounded-full bg-emerald-500 transition-all" style={{ width: `${completeness}%` }} />
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label={`Activities · ${withEvidence} with evidence`} value={acts.length} icon={Award} to="/app/activities" />
        <Stat label="CGPA" value={summary.data?.cgpa?.toFixed(2) ?? '–'} icon={GraduationCap} to="/app/academics" />
        <Stat label="Skills" value={skills.data?.length ?? 0} icon={Sparkles} to="/app/skills" />
      </div>

      <CompetencyProfile />

      <Card title="Recent activities" action={<Link to="/app/activities" className="text-sm text-slate-600 hover:underline">View all</Link>}>
        {acts.length === 0 ? (
          <p className="text-sm text-slate-500">No activities yet. Add your first project, certificate or event.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {acts.slice(0, 5).map((a) => (
              <li key={a.id} className="flex items-center justify-between gap-3 py-2.5">
                <Link to={`/app/activities/${a.id}`} className="min-w-0">
                  <div className="truncate text-sm font-medium">{a.title}</div>
                  <div className="text-xs text-slate-500">
                    {a.type.label} · {a.start_date}
                  </div>
                </Link>
                <EvidenceBadge status={a.evidence_status} />
              </li>
            ))}
          </ul>
        )}
      </Card>

    </div>
  )
}
