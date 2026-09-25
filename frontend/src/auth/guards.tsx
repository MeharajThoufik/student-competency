import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { Alert, Spinner } from '../components/ui'
import { useAuth } from './AuthProvider'

/** Signed in + consent given. Otherwise redirect to /login or /consent. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { firebaseUser, user, loading, error } = useAuth()
  const location = useLocation()

  if (loading) return <Spinner />
  if (!firebaseUser) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (error || !user)
    return (
      <div className="mx-auto max-w-md p-8">
        <Alert>Could not load your account: {error?.message ?? 'unknown error'}</Alert>
      </div>
    )
  if (!user.consent_given_at) return <Navigate to="/consent" replace />
  return <>{children}</>
}
