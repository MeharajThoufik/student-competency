export type Health = {
  status: string
  version: string
  environment: string
  database: 'ok' | 'unavailable' | 'not_configured'
}

export async function fetchHealth(): Promise<Health> {
  const res = await fetch('/api/health')
  if (!res.ok) throw new Error(`API returned ${res.status}`)
  return res.json()
}
