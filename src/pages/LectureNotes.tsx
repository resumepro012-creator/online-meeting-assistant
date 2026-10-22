import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, NotebookText, ArrowDownUp, ArrowUpRight, Copy, Download, Check } from 'lucide-react'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Input } from '@/components/common/Input'
import { Card } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import { EmptyState } from '@/components/common/EmptyState'
import * as classService from '@/services/classService'
import type { LectureNote } from '@/types'
import { formatDate, noteToMarkdown, downloadNoteAsMarkdown } from '@/lib/utils'

export default function LectureNotes() {
  const [notes, setNotes] = useState<LectureNote[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [subject, setSubject] = useState('All')
  const [sort, setSort] = useState<'newest' | 'oldest'>('newest')
  const [copiedId, setCopiedId] = useState<string | null>(null)

  useEffect(() => {
    classService.getAllNotes().then((n) => {
      setNotes(n)
      setLoading(false)
    })
  }, [])

  const subjects = useMemo(() => ['All', ...Array.from(new Set(notes.map((n) => n.subject)))], [notes])

  const filtered = useMemo(() => {
    let result = notes.filter(
      (n) => n.title.toLowerCase().includes(query.toLowerCase()) || n.preview.toLowerCase().includes(query.toLowerCase())
    )
    if (subject !== 'All') result = result.filter((n) => n.subject === subject)
    result = [...result].sort((a, b) => {
      const diff = new Date(a.date).getTime() - new Date(b.date).getTime()
      return sort === 'newest' ? -diff : diff
    })
    return result
  }, [notes, query, subject, sort])

  const handleCopy = async (note: LectureNote) => {
    await navigator.clipboard.writeText(noteToMarkdown(note))
    setCopiedId(note.id)
    setTimeout(() => setCopiedId(null), 1600)
  }

  return (
    <DashboardLayout title="Lecture Notes">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="flex-1">
          <Input
            placeholder="Search notes…"
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
          icon={NotebookText}
          title="No notes found"
          description={notes.length === 0 ? 'Notes appear here once a class finishes processing.' : 'Try a different search or filter.'}
        />
      ) : (
        <div className="space-y-4">
          {filtered.map((note) => (
            <Card key={note.id} className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="blue">{note.subject}</Badge>
                  <span className="text-xs text-muted">{formatDate(note.date)}</span>
                </div>
                <p className="mt-2 text-base font-semibold text-white">{note.title}</p>
                <p className="mt-1 line-clamp-2 max-w-2xl text-sm leading-relaxed text-muted">{note.preview}</p>
              </div>
              <div className="flex shrink-0 gap-2">
                <Link to={`/lecture-results/${note.classId}`}>
                  <button className="flex items-center gap-1.5 rounded-lg border border-card-border bg-card/60 px-3 py-2 text-xs text-white hover:border-primary/40">
                    <ArrowUpRight className="h-3.5 w-3.5" />
                    Open
                  </button>
                </Link>
                <button
                  onClick={() => handleCopy(note)}
                  className="flex items-center gap-1.5 rounded-lg border border-card-border bg-card/60 px-3 py-2 text-xs text-white hover:border-primary/40"
                >
                  {copiedId === note.id ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                  {copiedId === note.id ? 'Copied' : 'Copy'}
                </button>
                <button
                  onClick={() => downloadNoteAsMarkdown(note)}
                  className="flex items-center gap-1.5 rounded-lg border border-card-border bg-card/60 px-3 py-2 text-xs text-white hover:border-primary/40"
                >
                  <Download className="h-3.5 w-3.5" />
                  Download
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </DashboardLayout>
  )
}
