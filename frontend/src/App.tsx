import { useEffect, useState } from 'react'
import { fetchHealth, type Health } from './api'

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
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchHealth().then(setHealth).catch((e: Error) => setError(e.message))
  }, [])

  if (error) return <Badge tone="red">API offline: {error}</Badge>
  if (!health) return <Badge tone="gray">Checking API…</Badge>
  return (
    <div className="flex flex-wrap gap-2">
      <Badge tone="green">API {health.status} · v{health.version}</Badge>
      <Badge tone={health.database === 'ok' ? 'green' : 'gray'}>DB {health.database}</Badge>
      <Badge tone="gray">{health.environment}</Badge>
    </div>
  )
}

function Badge({ tone, children }: { tone: 'green' | 'red' | 'gray'; children: React.ReactNode }) {
  const tones = {
    green: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
    red: 'bg-rose-50 text-rose-700 ring-rose-600/20',
    gray: 'bg-slate-50 text-slate-600 ring-slate-500/20',
  }
  return (
    <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset ${tones[tone]}`}>
      {children}
    </span>
  )
}

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
          <span className="font-semibold">Competency Evolution</span>
          <button className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white opacity-60" disabled title="Available in P1">
            Login
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-16">
        <span className="inline-block rounded bg-rose-600 px-2 py-0.5 text-xs font-semibold text-white">SDG 4 · Quality Education</span>
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
