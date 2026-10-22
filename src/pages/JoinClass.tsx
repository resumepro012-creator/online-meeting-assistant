import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Radio, Mic, FileAudio, Square, Clock } from 'lucide-react'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { JoinClassForm } from '@/components/classes/JoinClassForm'
import { AIActivityVisual } from '@/components/classes/AIActivityVisual'
import { Card } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'
import * as classService from '@/services/classService'
import type { ClassSession } from '@/types'

export default function JoinClass() {
  const navigate = useNavigate()
  const [session, setSession] = useState<ClassSession | null>(null)
  const [lectureId, setLectureId] = useState<string | null>(null)
  const [hasAudio, setHasAudio] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirmEnd, setConfirmEnd] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [])

  const handleJoin = async ({
    title,
    subject,
    meetingLink,
    file,
  }: {
    title: string
    subject: string
    meetingLink: string
    file: File | null
  }) => {
    setIsSubmitting(true)
    setError(null)
    try {
      // Creates the class and uploads the recording. The backend queues the
      // processing job and hands back the lecture id the Processing page polls.
      const started = await classService.startSession({ title, subject, meetingLink, file })
      setSession(started.session)
      setLectureId(started.lectureId)
      setHasAudio(!!file)
      setElapsed(0)

      timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000)
    } catch (e) {
      setError(
        e instanceof classService.ApiError
          ? e.message
          : 'Could not start this class session. Is the backend running?'
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleEndClass = () => {
    if (timerRef.current) clearInterval(timerRef.current)
    if (session) {
      navigate(`/processing/${session.id}`, { state: { session, lectureId } })
    }
  }

  const mins = String(Math.floor(elapsed / 60)).padStart(2, '0')
  const secs = String(elapsed % 60).padStart(2, '0')

  return (
    <DashboardLayout title="Join Class">
      {!session ? (
        <div className="py-6">
          <div className="mx-auto mb-8 max-w-xl text-center">
            <h2 className="text-2xl font-semibold text-white">Start a New Class Session</h2>
            <p className="mt-2 text-sm text-muted">
              Upload the lecture recording or transcript, and the AI pipeline will process it for you.
            </p>
          </div>
          {error && (
            <div className="mx-auto mb-5 max-w-xl rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}
          <JoinClassForm onJoin={handleJoin} isSubmitting={isSubmitting} />
        </div>
      ) : (
        <div className="mx-auto max-w-2xl py-6">
          <Card strong className="text-center">
            <div className="mb-5 flex items-center justify-center gap-2">
              <Badge tone="cyan">
                <Radio className="h-3 w-3 animate-pulse" />
                Session Active
              </Badge>
            </div>

            <h2 className="text-xl font-semibold text-white">{session.title}</h2>
            <p className="mt-1 text-sm text-muted">{session.subject}</p>

            <div className="mt-8 flex justify-center">
              <AIActivityVisual size="lg" active />
            </div>

            <p className="mt-6 font-mono text-sm text-cyan">
              {hasAudio
                ? 'Recording ready — AI will process it when you end the session.'
                : 'No audio uploaded — live meeting capture is not available yet.'}
            </p>

            <div className="mx-auto mt-6 grid max-w-sm grid-cols-2 gap-3 text-left">
              <div className="rounded-xl border border-card-border bg-card/50 px-3.5 py-2.5">
                <p className="flex items-center gap-1.5 text-xs text-muted">
                  <Clock className="h-3.5 w-3.5" /> Elapsed
                </p>
                <p className="mt-1 font-mono text-sm text-white">
                  {mins}:{secs}
                </p>
              </div>
              <div className="rounded-xl border border-card-border bg-card/50 px-3.5 py-2.5">
                <p className="flex items-center gap-1.5 text-xs text-muted">
                  {hasAudio ? <FileAudio className="h-3.5 w-3.5" /> : <Mic className="h-3.5 w-3.5" />}
                  Audio Source
                </p>
                <p className="mt-1 text-sm text-white">{hasAudio ? 'Uploaded file' : 'None'}</p>
              </div>
            </div>

            <Button variant="danger" size="lg" className="mt-8" onClick={() => setConfirmEnd(true)}>
              <Square className="h-4 w-4" />
              End Class
            </Button>
          </Card>
        </div>
      )}

      <ConfirmDialog
        open={confirmEnd}
        title="End this class session?"
        description="The backend will transcribe the recording and generate the notes, questions and announcements. This cannot be undone."
        confirmLabel="End Class"
        destructive
        onConfirm={() => {
          setConfirmEnd(false)
          handleEndClass()
        }}
        onCancel={() => setConfirmEnd(false)}
      />
    </DashboardLayout>
  )
}
