import { auth } from './firebase'

// ---------- Types (mirror backend/app/schemas.py) ----------
export type Role = 'learner' | 'educator' | 'admin'

export type User = {
  id: number
  email: string
  name: string
  role: Role
  register_no: string | null
  programme: string | null
  department: string | null
  batch: string | null
  bio: string | null
  career_goals: string | null
  consent_given_at: string | null
}
export type UserUpdate = Partial<Omit<User, 'id' | 'email' | 'role' | 'consent_given_at'>>

export const GRADES = ['O', 'A+', 'A', 'B+', 'B', 'C', 'F', 'Ab'] as const
export type Grade = (typeof GRADES)[number]
export type AcademicIn = { semester: number; course_code: string; course_name: string; credits: number; grade: Grade }
export type Academic = AcademicIn & { id: number }
export type AcademicSummary = {
  semesters: { semester: number; credits: number; sgpa: number }[]
  cgpa: number | null
  total_credits: number
}

export const SKILL_CATEGORIES = ['technical', 'soft', 'domain', 'tool'] as const
export type SkillIn = { name: string; category: (typeof SKILL_CATEGORIES)[number]; self_level: number }
export type Skill = SkillIn & { id: number }
export type InterestIn = { tag: string; level: number }
export type Interest = InterestIn & { id: number; created_at: string }

export const OUTCOMES = ['participant', 'contributor', 'lead', 'completed', 'finalist', 'winner'] as const
export const SCOPES = ['personal', 'institute', 'state', 'national', 'international'] as const
export type ActivityType = { id: number; key: string; label: string; description: string | null }
export type ActivityIn = {
  type_id: number
  title: string
  description: string | null
  organization: string | null
  start_date: string
  end_date: string | null
  outcome: (typeof OUTCOMES)[number]
  scope: (typeof SCOPES)[number]
  skills: string[]
  url: string | null
}
export type Evidence = {
  id: number
  filename: string
  content_type: string
  size_bytes: number
  sha256: string
  uploaded_at: string
}
export type EvidenceStatus = 'self_reported' | 'evidence_attached' | 'verified'
export type Activity = Omit<ActivityIn, 'type_id'> & {
  id: number
  type: ActivityType
  verification_status: 'unverified' | 'verified' | 'rejected'
  evidence_status: EvidenceStatus
  review_note: string | null
  evidence: Evidence[]
  created_at: string
  updated_at: string
}

export type Contribution = {
  activity_id: number
  title: string
  type_key: string
  date: string
  weight: number
  level: number
  confidence: number
  decay: number
  points: number
}
export type CompetencyScore = { key: string; label: string; score: number; raw: number; contributions: Contribution[] }
export type LearnerCompetencies = { as_of: string; activity_count: number; scores: CompetencyScore[] }
export type ScoringConfig = {
  competencies: { key: string; label: string; description: string | null }[]
  activity_types: Record<string, string>
  weights: Record<string, Record<string, number>>
  half_life_months: number
  k: number
  confidence: Record<string, number>
  outcome: Record<string, number>
  scope: Record<string, number>
}

export type Trend = 'emerging' | 'improving' | 'stable' | 'declining' | 'inactive'
export type CompetencyTrend = {
  key: string
  label: string
  score: number
  previous: number
  change: number
  slope: number
  trend: Trend
  percentile: number | null
}
export type Recommendation = {
  kind: 'gap' | 'declining' | 'evidence'
  competency: string | null
  title: string
  detail: string
  gain: number
  activity_types: string[]
  activity_ids: number[]
}
export type TimelineEntry = {
  activity_id: number
  title: string
  type_key: string
  start_date: string
  end_date: string | null
  evidence_status: EvidenceStatus | 'rejected'
  deltas: Record<string, number>
}
export type InterestDrift = {
  since: string | null
  then: string[]
  now: string[]
  added: string[]
  removed: string[]
  drift: number | null
  history: { tag: string; level: number; added: string; removed: string | null }[]
}
export type Insights = {
  as_of: string
  window_months: number
  activity_count: number
  cohort_size: number
  series: { dates: string[]; scores: Record<string, number[]> }
  competencies: CompetencyTrend[]
  strengths: string[]
  gaps: string[]
  recommendations: Recommendation[]
  timeline: TimelineEntry[]
  interests: InterestDrift
}

// ---------- Educator ----------
export type Synthetic = 'exclude' | 'include' | 'only'
export type LearnerRef = { id: number; name: string; email: string; register_no: string | null; batch: string | null; synthetic: boolean }
export type ReviewQueue = { total: number; items: { learner: LearnerRef; activity: Activity }[] }
export type LearnerSummary = {
  learner: LearnerRef
  activity_count: number
  last_activity: string | null
  pending_reviews: number
  mean_score: number
  top_competency: string | null
  scores: Record<string, number>
  trends: Record<string, Trend>
  risks: string[]
}
export type LearnerList = { total: number; items: LearnerSummary[]; risk_rules: Record<string, string> }
export type LearnerDetail = {
  profile: User & { synthetic: boolean }
  academics: AcademicSummary
  skills: Skill[]
  interests: Interest[]
  activities: Activity[]
  insights: Insights
  risks: string[]
  risk_rules: Record<string, string>
}
export type CompetencyDistribution = {
  key: string
  label: string
  mean: number
  minimum: number
  p25: number
  median: number
  p75: number
  maximum: number
  trends: Record<Trend, number>
}
export type Cohort = {
  as_of: string
  learner_count: number
  active_count: number
  window_months: number
  competencies: CompetencyDistribution[]
  risk_counts: Record<string, number>
  risk_rules: Record<string, string>
  evidence: Record<string, number>
  activity_types: { key: string; label: string; count: number }[]
  batches: string[]
}

// ---------- Admin ----------
export type AdminUser = {
  id: number
  name: string
  email: string
  role: Role
  register_no: string | null
  batch: string | null
  consent_given_at: string | null
  last_login_at: string | null
}
export type AuditEntry = {
  id: number
  created_at: string
  actor: string | null
  action: string
  target_type: string
  target_id: number | null
  details: Record<string, unknown>
}
export type Weights = Record<string, Record<string, number>>
export type WeightImpact = {
  learners: number
  changed_weights: number
  mean_kendall_tau: number | null
  top_changed: number
  competencies: { key: string; label: string; kendall_tau: number | null; mean_change: number; max_abs_change: number }[]
}

// ---------- Learner groups (P5) ----------
export type Grouping = {
  as_of: string
  period_dates: string[]
  features: string
  k: number
  k_selection: { k: number; silhouette: number; davies_bouldin: number; inertia: number }[]
  algorithms: { name: string; n_clusters: number; noise: number; silhouette: number | null; davies_bouldin: number | null; ari: number | null; nmi: number | null }[]
  groups: { id: number; name: string; description: string; size: number; defining: string[]; mean_scores: Record<string, number>; lift: Record<string, number> }[]
  members: { learner: LearnerRef; states: number[]; position: [number, number] | null }[]
  pca_explained: number[]
  transitions: { source: number; target: number; learners: number }[][]
  movement_rate: number | null
  persona_agreement: { ari: number; nmi: number; contingency: Record<string, Record<string, number>> } | null
  notes: string[]
}

export type Health = {
  status: string
  version: string
  environment: string
  database: 'ok' | 'unavailable' | 'not_configured'
}

// ---------- Client ----------
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const token = await auth.currentUser?.getIdToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')

  const res = await fetch(`/api${path}`, { ...init, headers })
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res))
  if (res.status === 204) return undefined as T
  return res.json()
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) return body.detail.map((d: { msg: string }) => d.msg.replace(/^Value error, /, '')).join('; ')
  } catch {
    /* not JSON */
  }
  return `Request failed (${res.status})`
}

const json = (method: string, body?: unknown): RequestInit => ({ method, body: JSON.stringify(body) })

export const api = {
  health: () => request<Health>('/health'),

  me: () => request<User>('/me'),
  updateMe: (body: UserUpdate) => request<User>('/me', json('PATCH', body)),
  consent: () => request<User>('/me/consent', { method: 'POST' }),

  academics: () => request<Academic[]>('/me/academics'),
  academicSummary: () => request<AcademicSummary>('/me/academics/summary'),
  createAcademic: (body: AcademicIn) => request<Academic>('/me/academics', json('POST', body)),
  deleteAcademic: (id: number) => request<void>(`/me/academics/${id}`, { method: 'DELETE' }),

  skills: () => request<Skill[]>('/me/skills'),
  createSkill: (body: SkillIn) => request<Skill>('/me/skills', json('POST', body)),
  updateSkill: (id: number, body: SkillIn) => request<Skill>(`/me/skills/${id}`, json('PUT', body)),
  deleteSkill: (id: number) => request<void>(`/me/skills/${id}`, { method: 'DELETE' }),

  interests: () => request<Interest[]>('/me/interests'),
  createInterest: (body: InterestIn) => request<Interest>('/me/interests', json('POST', body)),
  deleteInterest: (id: number) => request<void>(`/me/interests/${id}`, { method: 'DELETE' }),

  activityTypes: () => request<ActivityType[]>('/activity-types'),
  activities: () => request<Activity[]>('/me/activities'),
  activity: (id: number) => request<Activity>(`/me/activities/${id}`),
  createActivity: (body: ActivityIn) => request<Activity>('/me/activities', json('POST', body)),
  updateActivity: (id: number, body: ActivityIn) => request<Activity>(`/me/activities/${id}`, json('PUT', body)),
  deleteActivity: (id: number) => request<void>(`/me/activities/${id}`, { method: 'DELETE' }),

  uploadEvidence: (activityId: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<Evidence>(`/me/activities/${activityId}/evidence`, { method: 'POST', body: form })
  },
  deleteEvidence: (id: number) => request<void>(`/evidence/${id}`, { method: 'DELETE' }),

  competencies: (asOf?: string) => request<LearnerCompetencies>(`/me/competencies${asOf ? `?as_of=${asOf}` : ''}`),
  scoringConfig: () => request<ScoringConfig>('/competencies/config'),
  insights: () => request<Insights>('/me/insights'),

  reviewQueue: (status: 'pending' | 'verified' | 'rejected', synthetic: Synthetic = 'exclude') =>
    request<ReviewQueue>(`/educator/queue?${new URLSearchParams({ status, synthetic })}`),
  review: (activityId: number, decision: 'verify' | 'reject', note: string | null) =>
    request<Activity>(`/educator/activities/${activityId}/review`, json('POST', { decision, note })),
  learners: (params: Record<string, string>) => request<LearnerList>(`/educator/learners?${new URLSearchParams(params)}`),
  learner: (id: number) => request<LearnerDetail>(`/educator/learners/${id}`),
  cohort: (params: Record<string, string>) => request<Cohort>(`/educator/cohort?${new URLSearchParams(params)}`),

  adminUsers: (q: string) => request<AdminUser[]>(`/admin/users?${new URLSearchParams(q ? { q } : {})}`),
  setRole: (id: number, role: Role) => request<AdminUser>(`/admin/users/${id}`, json('PATCH', { role })),
  updateWeights: (weights: Weights) => request<Weights>('/admin/weights', json('PUT', { weights })),
  resetWeights: () => request<Weights>('/admin/weights/reset', { method: 'POST' }),
  audit: () => request<AuditEntry[]>('/admin/audit?limit=200'),
  syntheticSummary: () => request<{ total: number; by_persona: Record<string, number> }>('/admin/synthetic'),
  generateSynthetic: (learners: number, seed: number) =>
    request<{ total: number; by_persona: Record<string, number> }>('/admin/synthetic', json('POST', { learners, seed })),
  clearSynthetic: () => request<{ total: number }>('/admin/synthetic', { method: 'DELETE' }),
  previewWeights: (weights: Weights) => request<WeightImpact>('/admin/weights/preview', json('POST', { weights })),
  groups: (params: Record<string, string>) => request<Grouping>(`/educator/groups?${new URLSearchParams(params)}`),
}

/** Download an authenticated file (e.g. a PDF report) using the name the server suggests. */
export async function downloadFile(path: string, fallbackName: string): Promise<void> {
  const token = await auth.currentUser?.getIdToken()
  const res = await fetch(`/api${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res))
  const name = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') ?? '')?.[1] ?? fallbackName
  const url = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
}

/** Evidence files need the auth header, so fetch as a blob and open it in a new tab. */
export async function openEvidence(id: number): Promise<void> {
  const tab = window.open('', '_blank')
  const token = await auth.currentUser?.getIdToken()
  const res = await fetch(`/api/evidence/${id}/file`, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) {
    tab?.close()
    throw new ApiError(res.status, await errorMessage(res))
  }
  const url = URL.createObjectURL(await res.blob())
  if (tab) tab.location.href = url
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}
