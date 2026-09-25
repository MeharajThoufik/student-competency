import { useQuery, useQueryClient } from '@tanstack/react-query'
import { onIdTokenChanged, signOut, type User as FirebaseUser } from 'firebase/auth'
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, type User } from '../lib/api'
import { auth } from '../lib/firebase'

type AuthState = {
  firebaseUser: FirebaseUser | null
  /** The app user from /api/me (role, consent, profile). */
  user: User | undefined
  loading: boolean
  error: Error | null
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [firebaseUser, setFirebaseUser] = useState<FirebaseUser | null>(null)
  const [initializing, setInitializing] = useState(true)
  const queryClient = useQueryClient()

  useEffect(
    () =>
      onIdTokenChanged(auth, (u) => {
        setFirebaseUser(u)
        setInitializing(false)
      }),
    [],
  )

  const me = useQuery({
    queryKey: ['me', firebaseUser?.uid],
    queryFn: api.me,
    enabled: !!firebaseUser,
    staleTime: 5 * 60_000,
  })

  const logout = async () => {
    await signOut(auth)
    queryClient.clear()
  }

  return (
    <AuthContext.Provider
      value={{
        firebaseUser,
        user: firebaseUser ? me.data : undefined,
        loading: initializing || (!!firebaseUser && me.isPending),
        error: me.error,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
