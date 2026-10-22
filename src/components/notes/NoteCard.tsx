import { Link } from 'react-router-dom'
import { Calendar, ArrowUpRight } from 'lucide-react'
import type { LectureNote } from '@/types'
import { Card } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import { formatDate } from '@/lib/utils'

export function NoteCard({ note }: { note: LectureNote }) {
  return (
    <Link to={`/lecture-results/${note.classId}`}>
      <Card hover className="flex h-full flex-col gap-3">
        <div className="flex items-start justify-between gap-3">
          <Badge tone="blue">{note.subject}</Badge>
          <ArrowUpRight className="h-4 w-4 shrink-0 text-muted" />
        </div>
        <div>
          <p className="text-base font-semibold text-white">{note.title}</p>
          <p className="mt-1.5 line-clamp-2 text-sm text-muted">{note.preview}</p>
        </div>
        <div className="mt-auto flex items-center gap-1.5 pt-2 text-xs text-muted">
          <Calendar className="h-3.5 w-3.5" />
          {formatDate(note.date)}
        </div>
      </Card>
    </Link>
  )
}
