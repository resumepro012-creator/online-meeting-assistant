import { Link } from 'react-router-dom'
import { Calendar, Clock, NotebookText } from 'lucide-react'
import type { ClassSession } from '@/types'
import { Card } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { formatDate } from '@/lib/utils'

const statusTone: Record<ClassSession['status'], { label: string; tone: 'green' | 'cyan' | 'amber' | 'neutral' }> = {
  completed: { label: 'Completed', tone: 'green' },
  live: { label: 'Live', tone: 'cyan' },
  processing: { label: 'Processing', tone: 'amber' },
  upcoming: { label: 'Upcoming', tone: 'neutral' },
}

export function ClassCard({ session }: { session: ClassSession }) {
  const status = statusTone[session.status]

  return (
    <Card className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-base font-semibold text-white">{session.title}</p>
          <p className="mt-0.5 text-sm text-muted">{session.subject}</p>
        </div>
        <Badge tone={status.tone}>{status.label}</Badge>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted">
        <span className="flex items-center gap-1.5">
          <Calendar className="h-3.5 w-3.5" />
          {formatDate(session.date)}
        </span>
        {session.durationMinutes && (
          <span className="flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5" />
            {session.durationMinutes} min
          </span>
        )}
      </div>

      {session.hasNotes ? (
        <Link to={`/lecture-results/${session.id}`}>
          <Button variant="secondary" size="sm" fullWidth>
            <NotebookText className="h-3.5 w-3.5" />
            View Notes
          </Button>
        </Link>
      ) : (
        <Button variant="ghost" size="sm" fullWidth disabled>
          Notes not ready yet
        </Button>
      )}
    </Card>
  )
}
