import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, Loader2, RefreshCw, Info } from 'lucide-react'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { AIActivityVisual } from '@/components/classes/AIActivityVisual'
import { Card } from '@/components/common/Card'
import { Button } from '@/components/common/Button'
import * as classService from '@/services/classService'
import type { ClassSession, ProcessingStage } from '@/types'
import { cn, sleep } from '@/lib/utils'

interface ProcessingRouteState {
  session?: ClassSession
  lectureId?: string | null
}

const POLL_INTERVAL_MS = 1000

export default function Processing() {
  const { classId } = useParams<{ classId: string }>()
  const location = useLocation() as { state?: ProcessingRouteState }
  const navigate = useNavigate()

  const [lectureId, setLectureId] = useState<string | null>(location.state?.lectureId ?? null)
  const [stages, setStages] = useState<ProcessingStage[]>(() => classService.getProcessingStages())
  const [stageKey, setStageKey] = useState('preparing')
  const [progress, setProgress] = useState(0)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [backendInfo, setBackendInfo] = useState<string | null>(null)
  const [retrying, setRetrying] = useState(false)
  const [attempt, setAttempt] = useState(0)

  // Report which implementations the backend is actually using, so a baseline
  // result can never be mistaken for a fine-tuned model result.
  useEffect(() => {
    let cancelled = false
    classService
      .getPipelineHealth()
      .then((health) => {
        if (cancelled) return
        const { speechToText, segmentClassifier } = health.pipeline
        setBackendInfo(`Speech-to-text: ${speechToText.backend} · Segment classifier: ${segmentClassifier.method}`)
      })
      .catch(() => {
        /* health is informational only — never blocks processing */
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | null = null

    /** Falls back to the class's most recent lecture so a page refresh works. */
    async function resolveLectureId(): Promise<string | null> {
      if (location.state?.lectureId) return location.state.lectureId
      if (!classId) return null
      const lectures = await classService.listClassLectures(classId)
      return lectures[0]?.id ?? null
    }

    async function poll(id: string) {
      try {
        const job = await classService.getJobStatus(id)
        if (cancelled) return

        if (job.stages.length) setStages(job.stages)
        setStageKey(job.stage)
        setProgress(job.progress)

        if (job.status === 'completed') {
          setDone(true)
          setProgress(100)
          await sleep(700)
          if (cancelled) return
          navigate(`/lecture-results/${job.courseId}`, { replace: true })
          return
        }

        if (job.status === 'failed') {
          setError(job.error ?? job.message ?? 'The backend reported that this processing job failed.')
          return
        }

        timer = setTimeout(() => poll(id), POLL_INTERVAL_MS)
      } catch (e) {
        if (cancelled) return
        setError(
          e instanceof classService.ApiError
            ? e.message
            : 'Lost contact with the backend while processing this lecture.'
        )
      }
    }

    async function run() {
      setError(null)
      setDone(false)
      setProgress(0)
      setStageKey('preparing')

      let id: string | null
      try {
        id = await resolveLectureId()
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof classService.ApiError ? e.message : 'Could not load this class session.')
        }
        return
      }
      if (cancelled) return

      if (!id) {
        setError(
          'No lecture recording was found for this class, so there is nothing to process. Start a session and upload an audio file or transcript first.'
        )
        return
      }

      setLectureId(id)
      await poll(id)
    }

    run()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt, classId, navigate])

  const handleRetry = async () => {
    if (!lectureId) return
    setRetrying(true)
    try {
      await classService.startProcessing(lectureId)
      setAttempt((n) => n + 1)
    } catch (e) {
      setError(e instanceof classService.ApiError ? e.message : 'Could not restart processing.')
    } finally {
      setRetrying(false)
    }
  }

  if (error) {
    return (
      <DashboardLayout title="AI Processing">
        <div className="mx-auto max-w-xl py-8">
          <Card strong className="text-center">
            <div className="flex justify-center">
              <AlertTriangle className="h-10 w-10 text-amber-300" />
            </div>
            <h2 className="mt-5 text-xl font-semibold text-white">Processing could not continue</h2>
            <p className="mt-2 text-sm text-muted">{error}</p>

            <div className="mt-7 flex flex-wrap justify-center gap-3">
              {lectureId && (
                <Button variant="primary" onClick={handleRetry} isLoading={retrying}>
                  <RefreshCw className="h-4 w-4" />
                  Retry processing
                </Button>
              )}
              <Link to="/join-class">
                <Button variant="secondary">Start a new session</Button>
              </Link>
              <Link to="/dashboard">
                <Button variant="ghost">Back to Dashboard</Button>
              </Link>
            </div>
          </Card>
        </div>
      </DashboardLayout>
    )
  }

  const activeIndex = Math.max(
    0,
    stages.findIndex((stage) => stage.key === stageKey)
  )
  const progressPct = done ? 100 : progress

  return (
    <DashboardLayout title="AI Processing">
      <div className="mx-auto max-w-xl py-8">
        <Card strong className="text-center">
          <div className="flex justify-center">
            <AIActivityVisual size="lg" active={!done} />
          </div>

          <h2 className="mt-6 text-xl font-semibold text-white">
            {done ? 'Processing Complete' : 'AI is Processing Your Lecture'}
          </h2>
          <p className="mt-1.5 text-sm text-muted">
            {done
              ? 'Redirecting to your lecture results…'
              : 'The backend is running the transcription, classification and note-generation pipeline.'}
          </p>

          <div className="mx-auto mt-6 h-2 w-full max-w-sm overflow-hidden rounded-full bg-card-border/60">
            <div
              className="h-full rounded-full btn-gradient transition-all duration-700 ease-out"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <p className="mt-2 font-mono text-xs text-muted">{progressPct}%</p>

          <ul className="mt-6 space-y-2.5 text-left">
            {stages.map((stage, i) => {
              const isActive = i === activeIndex && !done
              const isComplete = done || i < activeIndex
              return (
                <li
                  key={stage.key}
                  className={cn(
                    'flex items-center gap-3 rounded-xl border px-4 py-2.5 text-sm transition-colors duration-300',
                    isComplete
                      ? 'border-primary/30 bg-primary/5 text-white'
                      : isActive
                        ? 'border-cyan/40 bg-cyan/5 text-white'
                        : 'border-card-border/60 text-muted'
                  )}
                >
                  {isComplete ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-primary" />
                  ) : isActive ? (
                    <Loader2 className="h-4 w-4 shrink-0 animate-spin text-cyan" />
                  ) : (
                    <span className="h-4 w-4 shrink-0 rounded-full border border-card-border" />
                  )}
                  {stage.label}
                </li>
              )
            })}
          </ul>

          {backendInfo && (
            <div className="mt-6 flex items-start gap-2 rounded-xl border border-cyan/25 bg-cyan/10 px-3.5 py-2.5 text-left text-xs text-cyan">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <p>{backendInfo}</p>
            </div>
          )}
        </Card>
      </div>
    </DashboardLayout>
  )
}
