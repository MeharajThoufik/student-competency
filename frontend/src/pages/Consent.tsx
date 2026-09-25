import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { Alert, Button, Spinner } from '../components/ui'
import { api } from '../lib/api'

const POINTS = [
  'Your profile, academic records, activities and uploaded certificates are stored securely in Google Cloud (Mumbai region) and encrypted at rest.',
  'This information is used only to build your competency profile and the analytics shown to you.',
  'Educators may view your profile and evidence to verify achievements and give guidance.',
  'Aggregated, anonymised data may be used in the research study for this M.Tech case study.',
  'You can edit or delete your entries at any time.',
]

export function Consent() {
  const { firebaseUser, user, loading, logout } = useAuth()
  const queryClient = useQueryClient()
  const [agreed, setAgreed] = useState(false)
  const consent = useMutation({
    mutationFn: api.consent,
    onSuccess: (u) => queryClient.setQueryData(['me', firebaseUser?.uid], u),
  })

  if (loading) return <Spinner />
  if (!firebaseUser) return <Navigate to="/login" replace />
  if (user?.consent_given_at) return <Navigate to="/app" replace />

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10">
      <div className="w-full max-w-lg rounded-xl border border-slate-200 bg-white p-6">
        <ShieldCheck className="size-8 text-emerald-600" />
        <h1 className="mt-3 text-lg font-semibold">Before you start, {user?.name}</h1>
        <p className="mt-1 text-sm text-slate-600">Please review how your information is used.</p>
        <ul className="mt-5 space-y-3 text-sm text-slate-700">
          {POINTS.map((p) => (
            <li key={p} className="flex gap-2">
              <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-slate-400" /> {p}
            </li>
          ))}
        </ul>
        <label className="mt-6 flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-0.5" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
          I understand and agree to my information being used as described above.
        </label>
        {consent.error && (
          <div className="mt-4">
            <Alert>{consent.error.message}</Alert>
          </div>
        )}
        <div className="mt-6 flex justify-between">
          <Button variant="ghost" onClick={logout}>
            Sign out
          </Button>
          <Button disabled={!agreed} loading={consent.isPending} onClick={() => consent.mutate()}>
            Agree and continue
          </Button>
        </div>
      </div>
    </div>
  )
}
