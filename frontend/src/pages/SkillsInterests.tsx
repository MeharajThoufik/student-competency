import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Alert, Button, Card, Empty, Field, groupBy, Input, Level, Select, titleCase } from '../components/ui'
import { api, SKILL_CATEGORIES, type InterestIn, type SkillIn } from '../lib/api'

const LEVELS = ['Beginner', 'Elementary', 'Intermediate', 'Advanced', 'Expert']

function Skills() {
  const queryClient = useQueryClient()
  const skills = useQuery({ queryKey: ['skills'], queryFn: api.skills })
  const [form, setForm] = useState<SkillIn>({ name: '', category: 'technical', self_level: 3 })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['skills'] })
  const create = useMutation({
    mutationFn: api.createSkill,
    onSuccess: () => {
      refresh()
      setForm({ ...form, name: '' })
    },
  })
  const remove = useMutation({ mutationFn: api.deleteSkill, onSuccess: refresh })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    create.mutate(form)
  }

  const grouped = groupBy(skills.data ?? [], (s) => s.category)

  return (
    <Card title="Skills" action={<span className="text-xs text-slate-500">Self-rated</span>}>
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-4">
        <Field label="Skill" className="sm:col-span-2">
          <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Python, Public speaking" />
        </Field>
        <Field label="Category">
          <Select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value as SkillIn['category'] })}>
            {SKILL_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {titleCase(c)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Level">
          <Select value={form.self_level} onChange={(e) => setForm({ ...form, self_level: +e.target.value })}>
            {LEVELS.map((l, i) => (
              <option key={l} value={i + 1}>
                {i + 1} · {l}
              </option>
            ))}
          </Select>
        </Field>
        <div className="sm:col-span-4">
          <Button type="submit" loading={create.isPending}>
            Add skill
          </Button>
        </div>
        {create.error && (
          <div className="sm:col-span-4">
            <Alert>{create.error.message}</Alert>
          </div>
        )}
      </form>

      <div className="mt-6 space-y-5">
        {!skills.data?.length && <Empty>No skills added yet.</Empty>}
        {SKILL_CATEGORIES.filter((c) => grouped[c]?.length).map((c) => (
          <div key={c}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{titleCase(c)}</h3>
            <ul className="grid gap-2 sm:grid-cols-2">
              {grouped[c]!.map((s) => (
                <li key={s.id} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2">
                  <span className="text-sm font-medium">{s.name}</span>
                  <span className="flex items-center gap-3">
                    <Level value={s.self_level} />
                    <button onClick={() => remove.mutate(s.id)} className="text-slate-400 hover:text-rose-600" aria-label={`Remove ${s.name}`}>
                      <X className="size-4" />
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Card>
  )
}

function Interests() {
  const queryClient = useQueryClient()
  const interests = useQuery({ queryKey: ['interests'], queryFn: api.interests })
  const [form, setForm] = useState<InterestIn>({ tag: '', level: 3 })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['interests'] })
  const create = useMutation({
    mutationFn: api.createInterest,
    onSuccess: () => {
      refresh()
      setForm({ ...form, tag: '' })
    },
  })
  const remove = useMutation({ mutationFn: api.deleteInterest, onSuccess: refresh })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    create.mutate(form)
  }

  return (
    <Card title="Interests" action={<span className="text-xs text-slate-500">History is kept to show how interests change</span>}>
      <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
        <Field label="Interest" className="min-w-48 flex-1">
          <Input required value={form.tag} onChange={(e) => setForm({ ...form, tag: e.target.value })} placeholder="e.g. Cloud security" />
        </Field>
        <Field label="How strong?">
          <Select value={form.level} onChange={(e) => setForm({ ...form, level: +e.target.value })}>
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n}>{n}</option>
            ))}
          </Select>
        </Field>
        <Button type="submit" loading={create.isPending}>
          Add
        </Button>
      </form>
      {create.error && (
        <div className="mt-3">
          <Alert>{create.error.message}</Alert>
        </div>
      )}
      <div className="mt-5 flex flex-wrap gap-2">
        {!interests.data?.length && <Empty>No interests added yet.</Empty>}
        {interests.data?.map((i) => (
          <span key={i.id} className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 py-1 pl-3 pr-1.5 text-sm">
            {i.tag}
            <Level value={i.level} />
            <button onClick={() => remove.mutate(i.id)} className="rounded-full p-0.5 text-slate-400 hover:bg-rose-50 hover:text-rose-600" aria-label={`Remove ${i.tag}`}>
              <X className="size-3.5" />
            </button>
          </span>
        ))}
      </div>
    </Card>
  )
}

export function SkillsInterests() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Skills & Interests</h1>
      <Skills />
      <Interests />
    </div>
  )
}
