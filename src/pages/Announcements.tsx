import { useEffect, useMemo, useState } from 'react'
import { Search, Megaphone } from 'lucide-react'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Input } from '@/components/common/Input'
import { AnnouncementCard } from '@/components/announcements/AnnouncementCard'
import { EmptyState } from '@/components/common/EmptyState'
import * as classService from '@/services/classService'
import type { Announcement, AnnouncementCategory } from '@/types'
import { cn } from '@/lib/utils'

const categories: (AnnouncementCategory | 'All')[] = [
  'All',
  'Assignment',
  'Quiz',
  'Exam',
  'Deadline',
  'Schedule Change',
  'General Announcement',
]

export default function AnnouncementsPage() {
  const [announcements, setAnnouncements] = useState<Announcement[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState<(typeof categories)[number]>('All')

  useEffect(() => {
    classService.getAllAnnouncements().then((a) => {
      setAnnouncements(a)
      setLoading(false)
    })
  }, [])

  const filtered = useMemo(() => {
    return announcements.filter((a) => {
      const matchesQuery =
        a.text.toLowerCase().includes(query.toLowerCase()) || a.relatedLecture.toLowerCase().includes(query.toLowerCase())
      const matchesCategory = category === 'All' || a.category === category
      return matchesQuery && matchesCategory
    })
  }, [announcements, query, category])

  return (
    <DashboardLayout title="Announcements">
      <div className="mb-5">
        <Input
          placeholder="Search announcements…"
          icon={<Search className="h-4 w-4" />}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <div className="mb-6 flex flex-wrap gap-2">
        {categories.map((c) => (
          <button
            key={c}
            onClick={() => setCategory(c)}
            className={cn(
              'rounded-full border px-3.5 py-1.5 text-xs font-medium transition-colors',
              category === c
                ? 'border-primary/50 bg-primary/15 text-white'
                : 'border-card-border bg-card/50 text-muted hover:text-white'
            )}
          >
            {c}
          </button>
        ))}
      </div>

      {!loading && filtered.length === 0 ? (
        <EmptyState
          icon={Megaphone}
          title="No announcements found"
          description={announcements.length === 0 ? 'Announcements from your classes will show up here.' : 'Try a different search or category.'}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {filtered.map((a) => (
            <AnnouncementCard key={a.id} announcement={a} />
          ))}
        </div>
      )}
    </DashboardLayout>
  )
}
