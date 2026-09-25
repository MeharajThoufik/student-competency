import { FirebaseError } from 'firebase/app'
import {
  createUserWithEmailAndPassword,
  sendEmailVerification,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signInWithPopup,
  updateProfile,
} from 'firebase/auth'
import { useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { Alert, Button, Field, Input } from '../components/ui'
import { api } from '../lib/api'
import { auth, googleProvider } from '../lib/firebase'

const MESSAGES: Record<string, string> = {
  'auth/invalid-credential': 'Incorrect email or password.',
  'auth/email-already-in-use': 'An account with this email already exists. Sign in instead.',
  'auth/weak-password': 'Password must be at least 6 characters.',
  'auth/invalid-email': 'Enter a valid email address.',
  'auth/popup-closed-by-user': 'Google sign-in was cancelled.',
  'auth/too-many-requests': 'Too many attempts. Try again in a few minutes.',
  'auth/operation-not-allowed': 'This sign-in method is not enabled yet in Firebase.',
}

const describe = (e: unknown) =>
  e instanceof FirebaseError ? (MESSAGES[e.code] ?? e.message) : e instanceof Error ? e.message : 'Something went wrong'

export function Login() {
  const { firebaseUser } = useAuth()
  const location = useLocation()
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const from = (location.state as { from?: string } | null)?.from ?? '/app'
  if (firebaseUser) return <Navigate to={from} replace />

  const run = async (fn: () => Promise<unknown>) => {
    setError(null)
    setInfo(null)
    setBusy(true)
    try {
      await fn()
    } catch (e) {
      setError(describe(e))
    } finally {
      setBusy(false)
    }
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    run(async () => {
      if (mode === 'signin') {
        await signInWithEmailAndPassword(auth, email, password)
      } else {
        const cred = await createUserWithEmailAndPassword(auth, email, password)
        await updateProfile(cred.user, { displayName: name })
        await sendEmailVerification(cred.user)
        const updated = await api.updateMe({ name })
        queryClient.setQueryData(['me', cred.user.uid], updated)
      }
    })
  }

  const resetPassword = () =>
    run(async () => {
      if (!email) throw new Error('Enter your email first.')
      await sendPasswordResetEmail(auth, email)
      setInfo('Password reset email sent.')
    })

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm">
        <Link to="/" className="mb-6 block text-center font-semibold">
          Competency Evolution
        </Link>
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h1 className="text-lg font-semibold">{mode === 'signin' ? 'Sign in' : 'Create your account'}</h1>

          <Button variant="secondary" className="mt-5 w-full" onClick={() => run(() => signInWithPopup(auth, googleProvider))} disabled={busy}>
            <svg className="size-4" viewBox="0 0 48 48" aria-hidden>
              <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
              <path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
              <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
              <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
            </svg>
            Continue with Google
          </Button>

          <div className="my-5 flex items-center gap-3 text-xs text-slate-400">
            <span className="h-px flex-1 bg-slate-200" /> or <span className="h-px flex-1 bg-slate-200" />
          </div>

          <form onSubmit={submit} className="space-y-4">
            {mode === 'signup' && (
              <Field label="Full name">
                <Input required value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
              </Field>
            )}
            <Field label="Email">
              <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            </Field>
            <Field label="Password">
              <Input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
              />
            </Field>
            {error && <Alert>{error}</Alert>}
            {info && <Alert tone="blue">{info}</Alert>}
            <Button type="submit" className="w-full" loading={busy}>
              {mode === 'signin' ? 'Sign in' : 'Create account'}
            </Button>
          </form>

          <div className="mt-4 flex justify-between text-sm">
            <button className="text-slate-600 hover:underline" onClick={() => setMode(mode === 'signin' ? 'signup' : 'signin')}>
              {mode === 'signin' ? 'Create an account' : 'Have an account? Sign in'}
            </button>
            {mode === 'signin' && (
              <button className="text-slate-600 hover:underline" onClick={resetPassword}>
                Forgot password?
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
