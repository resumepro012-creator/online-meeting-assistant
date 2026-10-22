import { CalendarClock, FileText, HelpCircle, AlertOctagon, Clock3, CalendarCog, Megaphone } from 'lucide-react'
import type { Announcement, AnnouncementCategory } from '@/types'
import { Card } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import { formatDate } from '@/lib/utils'

const categoryMeta: Record<AnnouncementCategory, { tone: 'blue' | 'violet' | 'red' | 'amber' | 'cyan' | 'neutral'; icon: typeof FileText }> = {
  Assignment: { tone: 'blue', icon: FileText },
  Quiz: { tone: 'violet', icon: HelpCircle },
  Exam: { tone: 'red', icon: AlertOctagon },
  Deadline: { tone: 'amber', icon: Clock3 },
  'Schedule Change': { tone: 'cyan', icon: CalendarCog },
  'General Announcement': { tone: 'neutral', icon: Megaphone },
}

export function AnnouncementCard({ announcement }: { announcement: Announcement }) {
  const meta = categoryMeta[announcement.category]
  const Icon = meta.icon

  return (
    <Card className="flex flex-col gap-3 border-l-2 border-l-primary/50">
      <div className="flex items-start justify-between gap-3">
        <Badge tone={meta.tone}>
          <Icon className="h-3 w-3" />
          {announcement.category}
        </Badge>
        <span className="shrink-0 text-xs text-muted">{formatDate(announcement.date)}</span>
      </div>

      <p className="text-sm leading-relaxed text-white/90">{announcement.text}</p>

      <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-xs text-muted">
        <span className="truncate">From: {announcement.relatedLecture}</span>
        {announcement.deadline && (
          <span className="flex items-center gap-1.5 text-cyan">
            <CalendarClock className="h-3.5 w-3.5" />
            Due {formatDate(announcement.deadline)}
          </span>
        )}
      </div>
    </Card>
  )
}
