import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { Calendar, Clock, Download, Copy, Check, ArrowLeft, Megaphone, ListChecks, HelpCircle, ClipboardList, FileText } from 'lucide-react'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Card } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { EmptyState } from '@/components/common/EmptyState'
import { AnnouncementCard } from '@/components/announcements/AnnouncementCard'
import * as classService from '@/services/classService'
import type { ActionItem, Announcement, ClassResults, ClassSession, LectureNote, Question } from '@/types'
import { formatDate, noteToMarkdown, downloadNoteAsMarkdown, downloadClassSummaryAsPdf } from '@/lib/utils'

export default function LectureResults() {
  const { classId } = useParams<{ classId: string }>()
  const location = useLocation() as { state?: { session?: ClassSession; note?: LectureNote; announcements?: Announcement[] } }
  const [session, setSession] = useState<ClassSession | undefined>(location.state?.session)
  const [note, setNote] = useState<LectureNote | undefined>(location.state?.note)
  const [announcements, setAnnouncements] = useState<Announcement[]>(location.state?.announcements ?? [])
  const [questions, setQuestions] = useState<Question[]>([])
  const [actionItems, setActionItems] = useState<ActionItem[]>([])
  const [fullResults, setFullResults] = useState<ClassResults | null>(null)
  const [loading, setLoading] = useState(!location.state?.note)
  const [copied, setCopied] = useState(false)
  const [pdfGenerating, setPdfGenerating] = useState(false)

  useEffect(() => {
    if (location.state?.note || !classId) {
      setLoading(false)
      return
    }
    let cancelled = false
    async function load() {
      const [s, results] = await Promise.all([
        classService.getClassById(classId!),
        classService.getClassResults(classId!),
      ])
      if (cancelled) return
      setSession(s)
      setNote(results.note ?? undefined)
      setAnnouncements(results.announcements)
      setQuestions(results.questions ?? [])
      setActionItems(results.actionItems ?? [])
      setFullResults(results)
      setLoading(false)
    }
    load()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [classId])

  const handleCopy = async () => {
    if (!note) return
    await navigator.clipboard.writeText(noteToMarkdown(note))
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }

  const handleDownload = () => {
    if (!note) return
    downloadNoteAsMarkdown(note)
  }

  const handleDownloadPdf = () => {
    if (!session) return
    const results: ClassResults = fullResults ?? {
      courseId: session.id,
      note: note ?? null,
      announcements,
      questions,
      actionItems,
    }
    setPdfGenerating(true)
    try {
      downloadClassSummaryAsPdf(results, note?.title ?? session.title, session.subject)
    } finally {
      setPdfGenerating(false)
    }
  }

  if (loading) {
    return (
      <DashboardLayout title="Lecture Results">
        <div className="py-24 text-center text-sm text-muted">Loading lecture results…</div>
      </DashboardLayout>
    )
  }

  if (!note || !session) {
    return (
      <DashboardLayout title="Lecture Results">
        <EmptyState
          title="No results found"
          description="We couldn't find lecture results for this class."
          action={
            <Link to="/dashboard">
              <Button size="sm">Back to Dashboard</Button>
            </Link>
          }
        />
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout title="Lecture Results">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <Badge tone="blue" className="mb-2">
            {session.subject}
          </Badge>
          <h2 className="text-2xl font-semibold text-white">{note.title}</h2>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
            <span className="flex items-center gap-1.5">
              <Calendar className="h-4 w-4" /> {formatDate(note.date)}
            </span>
            {session.durationMinutes && (
              <span className="flex items-center gap-1.5">
                <Clock className="h-4 w-4" /> {session.durationMinutes} min
              </span>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={handleCopy}>
            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? 'Copied' : 'Copy Notes'}
          </Button>
          <Button variant="secondary" size="sm" onClick={handleDownload}>
            <Download className="h-3.5 w-3.5" />
            Download
          </Button>
          <Button variant="primary" size="sm" onClick={handleDownloadPdf} disabled={pdfGenerating}>
            <FileText className="h-3.5 w-3.5" />
            {pdfGenerating ? 'Generating…' : 'Download PDF'}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <h3 className="mb-2 text-base font-semibold text-white">Lecture Summary</h3>
            <p className="text-sm leading-relaxed text-muted">{note.summary}</p>
          </Card>

          <Card>
            <h3 className="mb-3 flex items-center gap-2 text-base font-semibold text-white">
              <ListChecks className="h-4.5 w-4.5 text-primary" />
              Important Topics
            </h3>
            <div className="flex flex-wrap gap-2">
              {note.topics.map((t) => (
                <Badge key={t} tone="cyan">
                  {t}
                </Badge>
              ))}
            </div>
          </Card>

          <Card>
            <h3 className="mb-4 text-base font-semibold text-white">Lecture Notes</h3>
            <div className="space-y-6">
              {note.sections.map((section) => (
                <div key={section.heading}>
                  <p className="mb-2 text-sm font-semibold text-cyan">{section.heading}</p>
                  <ul className="space-y-1.5">
                    {section.points.map((point, i) => (
                      <li key={i} className="flex gap-2.5 text-sm leading-relaxed text-white/85">
                        <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-primary" />
                        {point}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </Card>

          {questions.length > 0 && (
            <Card>
              <h3 className="mb-3 flex items-center gap-2 text-base font-semibold text-white">
                <HelpCircle className="h-4.5 w-4.5 text-primary" />
                Questions Raised ({questions.length})
              </h3>
              <ul className="space-y-3">
                {questions.map((q) => (
                  <li key={q.id} className="flex gap-2.5 text-sm leading-relaxed text-white/85">
                    <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-cyan" />
                    <div>
                      {q.speaker && <span className="font-semibold text-cyan">{q.speaker}: </span>}
                      {q.text}
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {actionItems.length > 0 && (
            <Card>
              <h3 className="mb-3 flex items-center gap-2 text-base font-semibold text-white">
                <ClipboardList className="h-4.5 w-4.5 text-primary" />
                Action Items ({actionItems.length})
              </h3>
              <ul className="space-y-3">
                {actionItems.map((item) => (
                  <li key={item.id} className="flex gap-2.5 text-sm leading-relaxed text-white/85">
                    <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-primary" />
                    <div>
                      {item.assignee && <span className="font-semibold text-primary">[{item.assignee}] </span>}
                      {item.text}
                      {(item.dueAt || item.dueText) && (
                        <span className="ml-2 rounded bg-amber-500/15 px-2 py-0.5 text-xs text-amber-300">
                          Due: {item.dueAt ? formatDate(item.dueAt) : item.dueText}
                        </span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>

        <div className="space-y-4">
          <h3 className="flex items-center gap-2 text-base font-semibold text-white">
            <Megaphone className="h-4.5 w-4.5 text-primary" />
            Important Announcements
          </h3>
          {announcements.length === 0 ? (
            <EmptyState title="No announcements" description="Nothing flagged as an announcement in this lecture." />
          ) : (
            <div className="space-y-4">
              {announcements.map((a) => (
                <AnnouncementCard key={a.id} announcement={a} />
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="mt-8">
        <Link to="/dashboard">
          <Button variant="secondary" size="md">
            <ArrowLeft className="h-4 w-4" />
            Back to Dashboard
          </Button>
        </Link>
      </div>
    </DashboardLayout>
  )
}
