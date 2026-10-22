import { useEffect, useMemo, useState } from 'react'
import { Search, History, ArrowDownUp } from 'lucide-react'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Input } from '@/components/common/Input'
import { ClassCard } from '@/components/classes/ClassCard'
import { EmptyState } from '@/components/common/EmptyState'
import * as classService from '@/services/classService'
import type { ClassSession } from '@/types'

export default function MyClasses() {
  const [classes, setClasses] = useState<ClassSession[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [subject, setSubject] = useState('All')
  const [sort, setSort] = useState<'newest' | 'oldest'>('newest')

  useEffect(() => {
    classService.getPreviousClasses().then((c) => {
      setClasses(c)
      setLoading(false)
    })
  }, [])

  const subjects = useMemo(() => ['All', ...Array.from(new Set(classes.map((c) => c.subject)))], [classes])

  const filtered = useMemo(() => {
    let result = classes.filter((c) => c.title.toLowerCase().includes(query.toLowerCase()))
    if (subject !== 'All') result = result.filter((c) => c.subject === subject)
    result = [...result].sort((a, b) => {
      const diff = new Date(a.date).getTime() - new Date(b.date).getTime()
      return sort === 'newest' ? -diff : diff
    })
    return result
  }, [classes, query, subject, sort])

  return (
    <DashboardLayout title="My Classes">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="flex-1">
          <Input
            placeholder="Search classes by title…"
            icon={<Search className="h-4 w-4" />}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <select
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          className="rounded-xl border border-card-border bg-card/70 px-4 py-2.5 text-sm text-white focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/25"
        >
          {subjects.map((s) => (
            <option key={s} value={s} className="bg-card text-white">
              {s}
            </option>
          ))}
        </select>
        <button
          onClick={() => setSort((s) => (s === 'newest' ? 'oldest' : 'newest'))}
          className="flex items-center gap-2 rounded-xl border border-card-border bg-card/70 px-4 py-2.5 text-sm text-white hover:border-primary/40"
        >
          <ArrowDownUp className="h-4 w-4 text-muted" />
          {sort === 'newest' ? 'Newest first' : 'Oldest first'}
        </button>
      </div>

      {!loading && filtered.length === 0 ? (
        <EmptyState
          icon={History}
          title="No classes found"
          description={classes.length === 0 ? 'Join your first class to see it appear here.' : 'Try a different search or filter.'}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((c) => (
            <ClassCard key={c.id} session={c} />
          ))}
        </div>
      )}
    </DashboardLayout>
  )
}
