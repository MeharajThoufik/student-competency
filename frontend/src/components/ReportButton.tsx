import { FileDown } from 'lucide-react'
import { useState } from 'react'
import { downloadFile } from '../lib/api'
import { Button } from './ui'

/** Downloads the PDF competency report. `learnerId` for educators; omit for the signed-in learner. */
export function ReportButton({ learnerId }: { learnerId?: number }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const path = learnerId ? `/educator/learners/${learnerId}/report.pdf` : '/me/report.pdf'
  return (
    <span className="inline-flex flex-col items-end gap-1">
      <Button
        variant="secondary"
        loading={busy}
        onClick={async () => {
          setBusy(true)
          setError(null)
          try {
            await downloadFile(path, 'competency-report.pdf')
          } catch (e) {
            setError((e as Error).message)
          } finally {
            setBusy(false)
          }
        }}
      >
        {!busy && <FileDown className="size-4" />} PDF report
      </Button>
      {error && <span className="text-xs text-rose-700">{error}</span>}
    </span>
  )
}
