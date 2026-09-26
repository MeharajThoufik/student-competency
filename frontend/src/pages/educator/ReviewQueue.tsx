import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ActivitySummary, DemoBadge, EvidenceLinks, ReviewActions, SyntheticSelect } from '../../components/educator'
import { Alert, Card, Empty, Spinner } from '../../components/ui'
import { api, type Synthetic } from '../../lib/api'

const TABS = [
  { key: 'pending', label: 'Pending' },
  { key: 'verified', label: 'Verified' },
  { key: 'rejected', label: 'Rejected' },
] as const

export function ReviewQueue() {
  const [tab, setTab] = useState<(typeof TABS)[number]['key']>('pending')
  const [synthetic, setSynthetic] = useState<Synthetic>('exclude')
  const queue = useQuery({ queryKey: ['review-queue', tab, synthetic], queryFn: () => api.reviewQueue(tab, synthetic) })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Review queue</h1>
        <p className="text-sm text-slate-500">
          Check the evidence learners attach. Verified activities count fully (×1.0) in their competency scores; rejected ones count ×0.25.
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex rounded-lg bg-slate-100 p-1" role="tablist">
          {TABS.map((t) => (
            <button
              key={t.key}
              role="tab"
              aria-selected={tab === t.key}
              onClick={() => setTab(t.key)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium ${tab === t.key ? 'bg-white shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
            >
              {t.label}
              {tab === t.key && queue.data && <span className="ml-1.5 text-slate-500">{queue.data.total}</span>}
            </button>
          ))}
        </div>
        <SyntheticSelect value={synthetic} onChange={setSynthetic} />
      </div>

      {queue.isPending ? (
        <Spinner />
      ) : queue.error ? (
        <Alert>{queue.error.message}</Alert>
      ) : !queue.data.items.length ? (
        <Empty>{tab === 'pending' ? 'Nothing to review. Activities appear here when a learner attaches evidence.' : `No ${tab} activities.`}</Empty>
      ) : (
        <ul className="space-y-4">
          {queue.data.items.map(({ learner, activity }) => (
            <li key={activity.id}>
              <Card>
                <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
                  <Link to={`/app/educator/learners/${learner.id}`} className="font-semibold hover:underline">
                    {learner.name}
                  </Link>
                  <span className="text-slate-500">
                    {[learner.register_no, learner.batch].filter(Boolean).join(' · ') || learner.email}
                  </span>
                  {learner.synthetic && <DemoBadge />}
                </div>
                <ActivitySummary activity={activity}>
                  <EvidenceLinks activity={activity} />
                </ActivitySummary>
                <div className="mt-4 border-t border-slate-100 pt-3">
                  <ReviewActions activity={activity} />
                </div>
              </Card>
            </li>
          ))}
          {queue.data.total > queue.data.items.length && (
            <li className="text-center text-sm text-slate-500">Showing the first {queue.data.items.length} of {queue.data.total}.</li>
          )}
        </ul>
      )}
    </div>
  )
}
