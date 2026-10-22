import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BookOpen, CheckCircle2, NotebookText, Megaphone, Video, ArrowRight } from 'lucide-react'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { StatCard } from '@/components/common/StatCard'
import { Button } from '@/components/common/Button'
import { EmptyState } from '@/components/common/EmptyState'
import { ClassCard } from '@/components/classes/ClassCard'
import { NoteCard } from '@/components/notes/NoteCard'
import { AnnouncementCard } from '@/components/announcements/AnnouncementCard'
import { useAuth } from '@/hooks/useAuth'
import * as classService from '@/services/classService'
import type { Announcement, ClassSession, DashboardSummary, LectureNote } from '@/types'

export default function Dashboard() {
  const { student } = useAuth()
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [recentClasses, setRecentClasses] = useState<ClassSession[]>([])
  const [recentNotes, setRecentNotes] = useState<LectureNote[]>([])
  const [announcements, setAnnouncements] = useState<Announcement[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function load() {
      const [s, c, n, a] = await Promise.all([
        classService.getDashboardSummary(),
        classService.getRecentClasses(3),
        classService.getRecentNotes(3),
        classService.getRecentAnnouncements(4),
      ])
      if (cancelled) return
      setSummary(s)
      setRecentClasses(c)
      setRecentNotes(n)
      setAnnouncements(a)
      setLoading(false)
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  const firstName = student?.name?.split(' ')[0] ?? 'Student'

  return (
    <DashboardLayout title="Dashboard">
      <div className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-white">Welcome Back, {firstName}!</h2>
          <p className="mt-1 text-sm text-muted">Here&apos;s what&apos;s waiting for you today.</p>
        </div>
        <Link to="/join-class">
          <Button variant="primary" size="lg" fullWidth className="sm:w-auto">
            <Video className="h-4 w-4" />
            Join a New Class
          </Button>
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total Classes" value={summary?.totalClasses ?? '—'} icon={BookOpen} tone="blue" />
        <StatCard label="Classes Attended" value={summary?.classesAttended ?? '—'} icon={CheckCircle2} tone="cyan" />
        <StatCard label="Notes Generated" value={summary?.notesGenerated ?? '—'} icon={NotebookText} tone="blue" />
        <StatCard label="Important Announcements" value={summary?.importantAnnouncements ?? '—'} icon={Megaphone} tone="cyan" />
      </div>

      {/* Recent classes */}
      <section className="mt-10">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">Recent Classes</h3>
          <Link to="/my-classes" className="flex items-center gap-1 text-sm text-primary hover:underline">
            View all <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
        {!loading && recentClasses.length === 0 ? (
          <EmptyState
            icon={Video}
            title="No classes yet"
            description="Join your first class to see it appear here."
            action={
              <Link to="/join-class">
                <Button size="sm">Join a Class</Button>
              </Link>
            }
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {recentClasses.map((c) => (
              <ClassCard key={c.id} session={c} />
            ))}
          </div>
        )}
      </section>

      {/* Recent notes */}
      <section className="mt-10">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">Recent Lecture Notes</h3>
          <Link to="/lecture-notes" className="flex items-center gap-1 text-sm text-primary hover:underline">
            View all <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
        {!loading && recentNotes.length === 0 ? (
          <EmptyState icon={NotebookText} title="No notes yet" description="Notes appear here once a class finishes processing." />
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {recentNotes.map((n) => (
              <NoteCard key={n.id} note={n} />
            ))}
          </div>
        )}
      </section>

      {/* Announcements */}
      <section className="mt-10">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">Important Announcements</h3>
          <Link to="/announcements" className="flex items-center gap-1 text-sm text-primary hover:underline">
            View all <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
        {!loading && announcements.length === 0 ? (
          <EmptyState icon={Megaphone} title="No announcements yet" description="Anything your teacher flags in class will show up here." />
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {announcements.map((a) => (
              <AnnouncementCard key={a.id} announcement={a} />
            ))}
          </div>
        )}
      </section>
    </DashboardLayout>
  )
}
