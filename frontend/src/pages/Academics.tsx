import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Alert, Button, Card, Empty, Field, groupBy, Input, Select, Spinner } from '../components/ui'
import { api, GRADES, type AcademicIn } from '../lib/api'

const blank: AcademicIn = { semester: 1, course_code: '', course_name: '', credits: 3, grade: 'A' }

export function Academics() {
  const queryClient = useQueryClient()
  const records = useQuery({ queryKey: ['academics'], queryFn: api.academics })
  const summary = useQuery({ queryKey: ['academic-summary'], queryFn: api.academicSummary })
  const [form, setForm] = useState<AcademicIn>(blank)

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['academics'] })
    queryClient.invalidateQueries({ queryKey: ['academic-summary'] })
  }
  const create = useMutation({
    mutationFn: api.createAcademic,
    onSuccess: () => {
      refresh()
      setForm({ ...blank, semester: form.semester })
    },
  })
  const remove = useMutation({ mutationFn: api.deleteAcademic, onSuccess: refresh })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    create.mutate(form)
  }

  const bySemester = groupBy(records.data ?? [], (r) => r.semester)
  const sgpa = new Map(summary.data?.semesters.map((s) => [s.semester, s.sgpa]))

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-2xl font-semibold">Academics</h1>
        <div className="text-right">
          <div className="text-2xl font-semibold">{summary.data?.cgpa?.toFixed(2) ?? '–'}</div>
          <div className="text-xs text-slate-500">CGPA · {summary.data?.total_credits ?? 0} credits</div>
        </div>
      </div>

      <Card title="Add course result">
        <form onSubmit={submit} className="grid gap-3 sm:grid-cols-6">
          <Field label="Semester">
            <Select value={form.semester} onChange={(e) => setForm({ ...form, semester: +e.target.value })}>
              {Array.from({ length: 10 }, (_, i) => (
                <option key={i + 1}>{i + 1}</option>
              ))}
            </Select>
          </Field>
          <Field label="Course code">
            <Input required value={form.course_code} onChange={(e) => setForm({ ...form, course_code: e.target.value })} />
          </Field>
          <Field label="Course name" className="sm:col-span-2">
            <Input required value={form.course_name} onChange={(e) => setForm({ ...form, course_name: e.target.value })} />
          </Field>
          <Field label="Credits">
            <Input
              type="number"
              min={0.5}
              max={30}
              step={0.5}
              required
              value={form.credits}
              onChange={(e) => setForm({ ...form, credits: +e.target.value })}
            />
          </Field>
          <Field label="Grade">
            <Select value={form.grade} onChange={(e) => setForm({ ...form, grade: e.target.value as AcademicIn['grade'] })}>
              {GRADES.map((g) => (
                <option key={g}>{g}</option>
              ))}
            </Select>
          </Field>
          <div className="sm:col-span-6">
            <Button type="submit" loading={create.isPending}>
              Add
            </Button>
          </div>
          {create.error && (
            <div className="sm:col-span-6">
              <Alert>{create.error.message}</Alert>
            </div>
          )}
        </form>
      </Card>

      {records.isPending ? (
        <Spinner />
      ) : !records.data?.length ? (
        <Empty>No course results yet.</Empty>
      ) : (
        Object.entries(bySemester).map(([sem, rows]) => (
          <Card key={sem} title={`Semester ${sem}`} action={<span className="text-sm text-slate-500">SGPA {sgpa.get(+sem)?.toFixed(2)}</span>}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs uppercase text-slate-500">
                  <tr>
                    <th className="pb-2 font-medium">Code</th>
                    <th className="pb-2 font-medium">Course</th>
                    <th className="pb-2 text-right font-medium">Credits</th>
                    <th className="pb-2 text-right font-medium">Grade</th>
                    <th />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {rows!.map((r) => (
                    <tr key={r.id}>
                      <td className="py-2 font-mono text-xs">{r.course_code}</td>
                      <td className="py-2">{r.course_name}</td>
                      <td className="py-2 text-right">{r.credits}</td>
                      <td className="py-2 text-right font-medium">{r.grade}</td>
                      <td className="py-2 text-right">
                        <button
                          onClick={() => remove.mutate(r.id)}
                          className="rounded p-1 text-slate-400 hover:bg-rose-50 hover:text-rose-600"
                          aria-label={`Delete ${r.course_code}`}
                        >
                          <Trash2 className="size-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        ))
      )}
    </div>
  )
}
