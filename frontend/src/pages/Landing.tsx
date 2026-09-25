import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { Badge } from '../components/ui'
import { api } from '../lib/api'

const COMPETENCIES = [
  'Technical',
  'Problem-Solving',
  'Communication',
  'Leadership',
  'Collaboration',
  'Creativity',
  'Research',
  'Continuous Learning',
]

function ApiStatus() {
  const { data, error, isPending } = useQuery({ queryKey: ['health'], queryFn: api.health, retry: false })
  if (error) return <Badge tone="red">API offline</Badge>
  if (isPending) return <Badge>Checking API…</Badge>
  return (
    <div className="flex flex-wrap gap-2">
      <Badge tone="green">API {data.status} · v{data.version}</Badge>
      <Badge tone={data.database === 'ok' ? 'green' : 'gray'}>DB {data.database}</Badge>
    </div>
  )
}

export function Landing() {
  const { firebaseUser } = useAuth()
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
          <span className="font-semibold">Competency Evolution</span>
          <Link
            to={firebaseUser ? '/app' : '/login'}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            {firebaseUser ? 'Open dashboard' : 'Login / Sign up'}
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-16">
        <span className="inline-block rounded bg-rose-600 px-2 py-0.5 text-xs font-semibold text-white">
          SDG 4 · Quality Education
        </span>
        <h1 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">
          Cloud-Based Continuous Competency Evolution Framework
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-slate-600">
          One unified learner profile that brings together academics, projects, certifications and achievements, and
          shows how each competency develops over time.
        </p>
        <div className="mt-8">
          <ApiStatus />
        </div>

        <section className="mt-16">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Competency dimensions</h2>
          <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {COMPETENCIES.map((c) => (
              <li key={c} className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm font-medium">
                {c}
              </li>
            ))}
          </ul>
        </section>
      </main>

      <footer className="mx-auto max-w-5xl px-4 py-8 text-xs text-slate-500">
        M.Tech Case Study · SRM Institute of Science and Technology
      </footer>
    </div>
  )
}
