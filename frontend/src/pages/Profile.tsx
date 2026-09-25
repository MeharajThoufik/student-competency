import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useAuth } from '../auth/AuthProvider'
import { Alert, Button, Card, Field, Input, Textarea } from '../components/ui'
import { api, type UserUpdate } from '../lib/api'

export function Profile() {
  const { user, firebaseUser } = useAuth()
  const queryClient = useQueryClient()
  const [form, setForm] = useState<UserUpdate>({
    name: user?.name ?? '',
    register_no: user?.register_no ?? '',
    programme: user?.programme ?? '',
    department: user?.department ?? '',
    batch: user?.batch ?? '',
    bio: user?.bio ?? '',
    career_goals: user?.career_goals ?? '',
  })
  const save = useMutation({
    mutationFn: () =>
      api.updateMe(Object.fromEntries(Object.entries(form).map(([k, v]) => [k, k === 'name' ? v : v || null]))),
    onSuccess: (u) => queryClient.setQueryData(['me', firebaseUser?.uid], u),
  })

  const set = (k: keyof UserUpdate) => (e: { target: { value: string } }) => {
    save.reset()
    setForm({ ...form, [k]: e.target.value })
  }
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Profile</h1>
      <Card title="Personal details">
        <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
          <Field label="Full name">
            <Input required value={form.name ?? ''} onChange={set('name')} />
          </Field>
          <Field label="Email">
            <Input value={user?.email ?? ''} disabled />
          </Field>
          <Field label="Register number">
            <Input value={form.register_no ?? ''} onChange={set('register_no')} placeholder="RA2512062015003" />
          </Field>
          <Field label="Batch">
            <Input value={form.batch ?? ''} onChange={set('batch')} placeholder="2025-2027" />
          </Field>
          <Field label="Programme">
            <Input value={form.programme ?? ''} onChange={set('programme')} placeholder="M.Tech Cloud Computing & Blockchain" />
          </Field>
          <Field label="Department">
            <Input value={form.department ?? ''} onChange={set('department')} placeholder="Computing Technologies" />
          </Field>
          <Field label="About me" className="sm:col-span-2">
            <Textarea value={form.bio ?? ''} onChange={set('bio')} />
          </Field>
          <Field label="Career goals" hint="Where do you want to be in 2–3 years?" className="sm:col-span-2">
            <Textarea value={form.career_goals ?? ''} onChange={set('career_goals')} />
          </Field>
          <div className="flex items-center gap-3 sm:col-span-2">
            <Button type="submit" loading={save.isPending}>
              Save changes
            </Button>
            {save.isSuccess && <span className="text-sm text-emerald-700">Saved</span>}
          </div>
          {save.error && (
            <div className="sm:col-span-2">
              <Alert>{save.error.message}</Alert>
            </div>
          )}
        </form>
      </Card>
    </div>
  )
}
