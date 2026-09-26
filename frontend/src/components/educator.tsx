import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Check, FileText, X } from 'lucide-react'
import { useState, type ReactElement, type ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { api, openEvidence, type Activity, type Role, type Synthetic } from '../lib/api'
import { Alert, Badge, Button, EvidenceBadge, Select, Textarea, titleCase } from './ui'

export const RISK_LABELS: Record<string, string> = {
  no_activity: 'No activity',
  inactive: 'Inactive',
  declining: 'Declining',
}

export function RiskBadges({ risks, rules }: { risks: string[]; rules?: Record<string, string> }) {
  if (!risks.length) return <span className="text-xs text-slate-400">—</span>
  return (
    <span className="flex flex-wrap gap-1">
      {risks.map((r) => (
        <span key={r} title={rules?.[r]}>
          <Badge tone={r === 'declining' ? 'red' : 'amber'}>
            <AlertTriangle className="size-3" /> {RISK_LABELS[r] ?? titleCase(r)}
          </Badge>
        </span>
      ))}
    </span>
  )
}

export function DemoBadge() {
  return (
    <span title="Generated demo learner (synthetic data)">
      <Badge>Demo</Badge>
    </span>
  )
}

export function SyntheticSelect({ value, onChange }: { value: Synthetic; onChange: (v: Synthetic) => void }) {
  return (
    <Select value={value} onChange={(e) => onChange(e.target.value as Synthetic)} className="w-auto" aria-label="Demo learners">
      <option value="exclude">Real learners</option>
      <option value="include">Real + demo learners</option>
      <option value="only">Demo learners only</option>
    </Select>
  )
}

export function RequireRole({ roles, children }: { roles: Role[]; children: ReactElement }) {
  const { user } = useAuth()
  return user && roles.includes(user.role) ? children : <Navigate to="/app" replace />
}

export function EvidenceLinks({ activity }: { activity: Activity }) {
  const [error, setError] = useState<string | null>(null)
  if (!activity.evidence.length) return <span className="text-xs text-slate-400">No evidence attached</span>
  return (
    <div>
      <div className="flex flex-wrap gap-1.5">
        {activity.evidence.map((ev) => (
          <button
            key={ev.id}
            type="button"
            onClick={() => {
              setError(null)
              openEvidence(ev.id).catch((e: Error) => setError(e.message))
            }}
            className="inline-flex max-w-full items-center gap-1.5 rounded-md border border-slate-200 px-2 py-1 text-xs hover:bg-slate-50"
          >
            <FileText className="size-3.5 shrink-0 text-slate-400" /> <span className="truncate">{ev.filename}</span>
          </button>
        ))}
      </div>
      {error && <p className="mt-1 text-xs text-rose-700">{error}</p>}
    </div>
  )
}

/** Verify / reject controls. A note is required to reject so the learner knows what to fix. */
export function ReviewActions({ activity, onDone }: { activity: Activity; onDone?: () => void }) {
  const queryClient = useQueryClient()
  const [rejecting, setRejecting] = useState(false)
  const [note, setNote] = useState('')
  const review = useMutation({
    mutationFn: (v: { decision: 'verify' | 'reject'; note: string | null }) => api.review(activity.id, v.decision, v.note),
    onSuccess: () => {
      setRejecting(false)
      setNote('')
      for (const key of ['review-queue', 'learners', 'learner', 'cohort']) queryClient.invalidateQueries({ queryKey: [key] })
      onDone?.()
    },
  })

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <EvidenceBadge status={activity.evidence_status as 'self_reported' | 'evidence_attached' | 'verified'} />
        {activity.verification_status === 'rejected' && <Badge tone="red">Rejected</Badge>}
        <span className="flex-1" />
        {activity.verification_status !== 'verified' && (
          <Button variant="secondary" className="py-1.5" loading={review.isPending && !rejecting} onClick={() => review.mutate({ decision: 'verify', note: note.trim() || null })}>
            <Check className="size-4" /> Verify
          </Button>
        )}
        {activity.verification_status !== 'rejected' && !rejecting && (
          <Button variant="danger" className="py-1.5" onClick={() => setRejecting(true)}>
            <X className="size-4" /> Reject
          </Button>
        )}
      </div>
      {rejecting && (
        <div className="space-y-2 rounded-lg bg-rose-50/60 p-3">
          <Textarea
            autoFocus
            rows={2}
            maxLength={1000}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="What should the learner fix? e.g. The certificate name doesn't match."
          />
          <div className="flex gap-2">
            <Button variant="danger" className="py-1.5 ring-1 ring-inset ring-rose-200" disabled={!note.trim()} loading={review.isPending} onClick={() => review.mutate({ decision: 'reject', note })}>
              Confirm reject
            </Button>
            <Button variant="ghost" className="py-1.5" onClick={() => setRejecting(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}
      {activity.review_note && !rejecting && <p className="text-xs text-slate-600">Review note: {activity.review_note}</p>}
      {review.error && <Alert>{review.error.message}</Alert>}
    </div>
  )
}

export function ActivitySummary({ activity, typeLabel, children }: { activity: Activity; typeLabel?: string; children?: ReactNode }) {
  return (
    <div className="space-y-2">
      <div>
        <div className="font-medium">{activity.title}</div>
        <div className="text-sm text-slate-500">
          {typeLabel ?? activity.type.label}
          {activity.organization && ` · ${activity.organization}`} · {activity.start_date}
          {activity.end_date && ` → ${activity.end_date}`} · {titleCase(activity.outcome)} · {titleCase(activity.scope)}
        </div>
      </div>
      {activity.description && <p className="whitespace-pre-line text-sm text-slate-700">{activity.description}</p>}
      {(activity.skills.length > 0 || activity.url) && (
        <div className="flex flex-wrap items-center gap-1.5">
          {activity.skills.map((s) => (
            <Badge key={s} tone="blue">
              {s}
            </Badge>
          ))}
          {activity.url && (
            <a href={activity.url} target="_blank" rel="noreferrer noopener" className="truncate text-xs text-sky-700 underline">
              {activity.url}
            </a>
          )}
        </div>
      )}
      {children}
    </div>
  )
}
