import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, FileText, Trash2, Upload, X } from 'lucide-react'
import { useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Alert, Badge, Button, Card, EvidenceBadge, Field, Input, Select, Spinner, Textarea, titleCase } from '../components/ui'
import { api, openEvidence, OUTCOMES, SCOPES, type Activity, type ActivityIn } from '../lib/api'

const MAX_MB = 10
const ACCEPT = 'application/pdf,image/png,image/jpeg,image/webp'
const today = () => new Date().toISOString().slice(0, 10)
const fmtSize = (b: number) => (b > 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1)} MB` : `${Math.ceil(b / 1024)} KB`)

export function ActivityForm() {
  const { id } = useParams()
  const existing = useQuery({ queryKey: ['activity', id], queryFn: () => api.activity(+id!), enabled: !!id })
  const types = useQuery({ queryKey: ['activity-types'], queryFn: api.activityTypes, staleTime: Infinity })

  if (types.isPending || (id && existing.isPending)) return <Spinner />
  if (existing.error) return <Alert>{existing.error.message}</Alert>
  return <Form key={id ?? 'new'} activity={existing.data} types={types.data ?? []} />
}

function Form({ activity, types }: { activity?: Activity; types: { id: number; label: string; description: string | null }[] }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const fileInput = useRef<HTMLInputElement>(null)
  const [form, setForm] = useState<ActivityIn>(
    activity
      ? {
          type_id: activity.type.id,
          title: activity.title,
          description: activity.description,
          organization: activity.organization,
          start_date: activity.start_date,
          end_date: activity.end_date,
          outcome: activity.outcome,
          scope: activity.scope,
          skills: activity.skills,
          url: activity.url,
        }
      : { type_id: types[0]?.id, title: '', description: null, organization: null, start_date: today(), end_date: null, outcome: 'participant', scope: 'institute', skills: [], url: null },
  )
  const [skillDraft, setSkillDraft] = useState('')
  const [pending, setPending] = useState<File[]>([])
  const [fileError, setFileError] = useState<string | null>(null)

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['activities'] })
    queryClient.invalidateQueries({ queryKey: ['activity'] })
  }

  // Set once the activity exists, so a retry after a failed upload updates instead of creating a duplicate.
  const [savedId, setSavedId] = useState(activity?.id)

  const save = useMutation({
    mutationFn: async () => {
      const body = { ...form, url: form.url || null, end_date: form.end_date || null }
      const saved = savedId ? await api.updateActivity(savedId, body) : await api.createActivity(body)
      setSavedId(saved.id)
      for (const file of pending) {
        await api.uploadEvidence(saved.id, file)
        setPending((p) => p.filter((f) => f !== file))
      }
      return saved
    },
    onSuccess: () => {
      invalidate()
      navigate('/app/activities')
    },
    onError: invalidate, // the activity may have been saved even if an upload failed
  })
  const remove = useMutation({
    mutationFn: () => api.deleteActivity(activity!.id),
    onSuccess: () => {
      invalidate()
      navigate('/app/activities')
    },
  })
  const removeEvidence = useMutation({ mutationFn: api.deleteEvidence, onSuccess: invalidate })
  const [viewError, setViewError] = useState<string | null>(null)

  const set = <K extends keyof ActivityIn>(k: K, v: ActivityIn[K]) => setForm({ ...form, [k]: v })

  const addSkill = () => {
    const s = skillDraft.trim().replace(/,$/, '')
    if (s && !form.skills.some((x) => x.toLowerCase() === s.toLowerCase()) && form.skills.length < 20) set('skills', [...form.skills, s])
    setSkillDraft('')
  }
  const onSkillKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      addSkill()
    }
  }

  const existingCount = activity?.evidence.length ?? 0
  const pickFiles = (files: FileList | null) => {
    setFileError(null)
    const next = [...pending]
    for (const f of Array.from(files ?? [])) {
      if (f.size > MAX_MB * 1024 * 1024) setFileError(`${f.name} is larger than ${MAX_MB} MB`)
      else if (!ACCEPT.split(',').includes(f.type)) setFileError(`${f.name}: only PDF, PNG, JPEG or WEBP`)
      else next.push(f)
    }
    if (existingCount + next.length > 5) setFileError('At most 5 files per activity')
    setPending(next.slice(0, Math.max(0, 5 - existingCount)))
    if (fileInput.current) fileInput.current.value = ''
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  const selectedType = types.find((t) => t.id === form.type_id)

  return (
    <div className="space-y-6">
      <Link to="/app/activities" className="inline-flex items-center gap-1 text-sm text-slate-600 hover:underline">
        <ArrowLeft className="size-4" /> Activities
      </Link>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">{activity ? 'Edit activity' : 'Add activity'}</h1>
        {activity && <EvidenceBadge status={activity.evidence_status} />}
      </div>
      {activity?.verification_status === 'verified' && (
        <Alert tone="blue">This activity is verified. Saving changes will send it back for verification.</Alert>
      )}
      {activity?.review_note && <Alert tone="blue">Educator note: {activity.review_note}</Alert>}

      <form onSubmit={submit} className="space-y-6">
        <Card title="Details">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Type" hint={selectedType?.description ?? undefined}>
              <Select value={form.type_id} onChange={(e) => set('type_id', +e.target.value)}>
                {types.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Title">
              <Input required maxLength={200} value={form.title} onChange={(e) => set('title', e.target.value)} placeholder="e.g. Smart India Hackathon 2026" />
            </Field>
            <Field label="Organization / issuer" hint="Who ran it or issued the certificate">
              <Input maxLength={200} value={form.organization ?? ''} onChange={(e) => set('organization', e.target.value)} />
            </Field>
            <Field label="Link" hint="Repo, credential URL or event page (optional)">
              <Input type="url" value={form.url ?? ''} onChange={(e) => set('url', e.target.value)} placeholder="https://" />
            </Field>
            <Field label="Start date">
              <Input type="date" required max={today()} value={form.start_date} onChange={(e) => set('start_date', e.target.value)} />
            </Field>
            <Field label="End date" hint="Leave empty for one-day or ongoing">
              <Input type="date" min={form.start_date} value={form.end_date ?? ''} onChange={(e) => set('end_date', e.target.value)} />
            </Field>
            <Field label="Your role / outcome">
              <Select value={form.outcome} onChange={(e) => set('outcome', e.target.value as ActivityIn['outcome'])}>
                {OUTCOMES.map((o) => (
                  <option key={o} value={o}>
                    {titleCase(o)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Level">
              <Select value={form.scope} onChange={(e) => set('scope', e.target.value as ActivityIn['scope'])}>
                {SCOPES.map((s) => (
                  <option key={s} value={s}>
                    {titleCase(s)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Description" hint="What did you do, and what did you learn?" className="sm:col-span-2">
              <Textarea rows={4} maxLength={5000} value={form.description ?? ''} onChange={(e) => set('description', e.target.value)} />
            </Field>
            <Field label="Skills used" hint="Press Enter or comma to add" className="sm:col-span-2">
              <div className="flex flex-wrap items-center gap-1.5 rounded-md bg-white p-1.5 ring-1 ring-inset ring-slate-300">
                {form.skills.map((s) => (
                  <Badge key={s} tone="blue">
                    {s}
                    <button type="button" onClick={() => set('skills', form.skills.filter((x) => x !== s))} aria-label={`Remove ${s}`}>
                      <X className="size-3" />
                    </button>
                  </Badge>
                ))}
                <input
                  className="min-w-32 flex-1 px-1.5 py-1 text-sm outline-none"
                  value={skillDraft}
                  onChange={(e) => setSkillDraft(e.target.value)}
                  onKeyDown={onSkillKey}
                  onBlur={addSkill}
                  placeholder={form.skills.length ? '' : 'e.g. Python, Teamwork'}
                />
              </div>
            </Field>
          </div>
        </Card>

        <Card title="Evidence" action={<span className="text-xs text-slate-500">PDF or image · max {MAX_MB} MB · up to 5</span>}>
          <p className="mb-4 text-sm text-slate-600">
            Attach a certificate, letter or screenshot. Activities with evidence count more, and educators can verify them.
          </p>
          <ul className="space-y-2">
            {activity?.evidence.map((ev) => (
              <li key={ev.id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2 text-sm">
                <button
                  type="button"
                  className="flex min-w-0 items-center gap-2 hover:underline"
                  onClick={() => {
                    setViewError(null)
                    openEvidence(ev.id).catch((e: Error) => setViewError(e.message))
                  }}
                >
                  <FileText className="size-4 shrink-0 text-slate-400" /> <span className="truncate">{ev.filename}</span>
                </button>
                <span className="flex shrink-0 items-center gap-3 text-xs text-slate-500">
                  {fmtSize(ev.size_bytes)}
                  <button type="button" onClick={() => removeEvidence.mutate(ev.id)} className="text-slate-400 hover:text-rose-600" aria-label="Delete file">
                    <Trash2 className="size-4" />
                  </button>
                </span>
              </li>
            ))}
            {pending.map((f, i) => (
              <li key={`${f.name}-${i}`} className="flex items-center justify-between gap-3 rounded-lg border border-dashed border-slate-300 px-3 py-2 text-sm">
                <span className="flex min-w-0 items-center gap-2">
                  <Upload className="size-4 shrink-0 text-slate-400" /> <span className="truncate">{f.name}</span>
                  <Badge>to upload</Badge>
                </span>
                <button type="button" onClick={() => setPending(pending.filter((_, j) => j !== i))} className="text-slate-400 hover:text-rose-600" aria-label="Remove file">
                  <X className="size-4" />
                </button>
              </li>
            ))}
          </ul>
          <input ref={fileInput} type="file" accept={ACCEPT} multiple className="hidden" onChange={(e) => pickFiles(e.target.files)} />
          <Button type="button" variant="secondary" className="mt-3" onClick={() => fileInput.current?.click()} disabled={existingCount + pending.length >= 5}>
            <Upload className="size-4" /> Choose files
          </Button>
          {fileError && <div className="mt-3"><Alert>{fileError}</Alert></div>}
          {viewError && <div className="mt-3"><Alert>{viewError}</Alert></div>}
        </Card>

        {save.error && <Alert>{save.error.message}</Alert>}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button type="submit" loading={save.isPending}>
            {activity ? 'Save changes' : 'Save activity'}
          </Button>
          {activity && (
            <Button
              type="button"
              variant="danger"
              loading={remove.isPending}
              onClick={() => {
                if (confirm('Delete this activity and its evidence?')) remove.mutate()
              }}
            >
              <Trash2 className="size-4" /> Delete activity
            </Button>
          )}
        </div>
      </form>
    </div>
  )
}
