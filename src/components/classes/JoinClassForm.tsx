import { useRef, useState, useEffect, type FormEvent } from 'react'
import { Video, Link2, BookMarked, Upload, FileAudio, X, Info, ShieldAlert, Mic, StopCircle } from 'lucide-react'
import { Input } from '@/components/common/Input'
import { Button } from '@/components/common/Button'
import { Card } from '@/components/common/Card'
import * as classService from '@/services/classService'
import type { MeetingPolicy } from '@/services/classService'
import { LiveAudioService, type LiveAudioState } from '@/services/LiveAudioService'

interface JoinClassFormProps {
  onJoin: (data: { title: string; subject: string; meetingLink: string; file: File | null }) => void
  isSubmitting: boolean
}

export function JoinClassForm({ onJoin, isSubmitting }: JoinClassFormProps) {
  const [title, setTitle] = useState('')
  const [subject, setSubject] = useState('')
  const [meetingLink, setMeetingLink] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [policy, setPolicy] = useState<MeetingPolicy | null>(null)
  const [liveState, setLiveState] = useState<LiveAudioState>({ status: 'idle', durationSeconds: 0 })
  const fileInputRef = useRef<HTMLInputElement>(null)
  const liveServiceRef = useRef<LiveAudioService | null>(null)

  useEffect(() => {
    liveServiceRef.current = new LiveAudioService(setLiveState)

    return () => {
      void liveServiceRef.current?.stop()
    }
  }, [])

  const handleStartLive = async () => {
    try {
      setErrors((prev) => ({ ...prev, session: '' }))
      setFile(null)
      await liveServiceRef.current?.start()
    } catch (err) {
      console.error('Live capture failed:', err)
      const message =
        err instanceof Error ? err.message : 'Could not start live capture'

      setLiveState({
        status: 'error',
        durationSeconds: 0,
        error: message,
      })
    }
  }

  const handleStopLive = async () => {
    const recordedFile = await liveServiceRef.current?.stop(
      `live_${Date.now()}.webm`,
    )

    if (!recordedFile) {
      setErrors((prev) => ({
        ...prev,
        session: 'No audio was captured. Make sure "Share tab audio" was enabled.',
      }))
      return null
    }

    setFile(recordedFile)
    return recordedFile
  }

  const validate = () => {
    const next: Record<string, string> = {}
    if (!title.trim()) next.title = 'Class title is required.'
    if (!subject.trim()) next.subject = 'Subject is required.'
    if (!file && liveState.status !== 'recording') {
      next.session = 'Upload a recording or start a live capture session.'
    }
    setErrors(next)
    return Object.keys(next).length === 0
  }

  const handleLinkBlur = async () => {
    const value = meetingLink.trim()
    if (!value) {
      setPolicy(null)
      return
    }
    try {
      setPolicy(await classService.getMeetingPolicy(value))
    } catch {
      setPolicy(null)
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()

    if (liveState.status === 'recording') {
      if (!title.trim()) {
        setErrors({ title: 'Class title is required.' })
        return
      }

      if (!subject.trim()) {
        setErrors({ subject: 'Subject is required.' })
        return
      }

      const recordedFile = await handleStopLive()

      if (recordedFile) {
        onJoin({
          title,
          subject,
          meetingLink,
          file: recordedFile,
        })
      }

      return
    }

    if (!validate()) return

    onJoin({
      title,
      subject,
      meetingLink,
      file,
    })
  }

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  return (
    <Card strong className="mx-auto w-full max-w-xl">
      <form onSubmit={handleSubmit} className="space-y-5">
        <Input
          label="Class Title"
          placeholder="e.g. Convolutional Neural Networks"
          icon={<BookMarked className="h-4 w-4" />}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          error={errors.title}
        />
        <Input
          label="Subject"
          placeholder="e.g. Deep Learning"
          icon={<Video className="h-4 w-4" />}
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          error={errors.subject}
        />
        <Input
          label="Online Class Meeting Link"
          placeholder="https://meet.example.com/your-class"
          icon={<Link2 className="h-4 w-4" />}
          value={meetingLink}
          onChange={(e) => {
            setMeetingLink(e.target.value)
            if (!e.target.value.trim()) setPolicy(null)
          }}
          onBlur={handleLinkBlur}
        />

        {policy && (
          <div className="rounded-xl border border-card-border bg-card/50 px-3.5 py-3 text-xs">
            <p className="flex items-center gap-1.5 font-medium text-white">
              <ShieldAlert className="h-3.5 w-3.5 text-primary" />
              {policy.platformName}
            </p>
            <p className="mt-1.5 text-muted">
              Open the meeting in your browser, then click "Start Live Capture"
              and select the meeting tab.
            </p>
            {policy.accessControls.length > 0 && (
              <ul className="mt-2 list-disc space-y-0.5 pl-4 text-muted">
                {policy.accessControls.map((control) => (
                  <li key={control}>{control}</li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-cyan">
              Tip: Make sure to check "Share tab audio" when selecting the meeting tab.
            </p>
          </div>
        )}

        <div className="flex items-center gap-3 text-xs text-muted">
          <span className="h-px flex-1 bg-card-border" />
          choose capture method
          <span className="h-px flex-1 bg-card-border" />
        </div>

        <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="mb-1.5 text-sm font-medium text-white/85">
                Live Capture
              </p>
              {liveState.status === 'recording' ? (
                <div className="flex flex-col items-center gap-2 rounded-xl border border-primary/50 bg-primary/10 px-4 py-6 text-center">
                  <div className="relative">
                    <StopCircle className="h-5 w-5 animate-pulse text-primary" />
                    <span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-red-500" />
                  </div>
                  <span className="text-sm font-medium text-white">
                    {`Recording: ${formatDuration(liveState.durationSeconds)}`}
                  </span>
                  <button
                    type="button"
                    onClick={handleStopLive}
                    className="mt-1 text-xs text-primary underline underline-offset-2 hover:text-primary/80"
                  >
                    Stop & Use Recording
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={handleStartLive}
                  disabled={false}
                  className="flex w-full flex-col items-center gap-2 rounded-xl border border-dashed border-card-border bg-card/40 px-4 py-6 text-center transition-colors hover:border-primary/50 disabled:opacity-50"
                >
                  <Mic className="h-5 w-5 text-muted" />
                  <span className="text-sm text-muted">
                    Start Live Capture
                  </span>
                </button>
              )}
            </div>

          <div>
            <p className="mb-1.5 text-sm font-medium text-white/85">Upload File</p>
            {!file ? (
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={liveState.status === 'recording'}
                className="flex w-full flex-col items-center gap-2 rounded-xl border border-dashed border-card-border bg-card/40 px-4 py-6 text-center transition-colors hover:border-primary/50 disabled:opacity-50"
              >
                <Upload className="h-5 w-5 text-muted" />
                <span className="text-sm text-muted">Select audio/transcript</span>
              </button>
            ) : (
              <div className="flex flex-col items-center gap-2 rounded-xl border border-card-border bg-card/60 px-4 py-6 text-center">
                <FileAudio className="h-5 w-5 text-primary" />
                <span className="w-full truncate text-sm text-white">{file.name}</span>
                <button
                  type="button"
                  onClick={() => {
                    setFile(null)
                    if (fileInputRef.current) fileInputRef.current.value = ''
                  }}
                  className="mt-1 text-xs text-red-400 underline underline-offset-2 hover:text-red-300"
                >
                  Remove
                </button>
              </div>
            )}
          </div>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept="audio/*,.txt,.vtt,.srt"
          className="hidden"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />

        {errors.session && <p className="text-xs text-red-400">{errors.session}</p>}
        {liveState.error && <p className="text-xs text-red-400">{liveState.error}</p>}

        <div className="flex items-start gap-2 rounded-xl border border-cyan/25 bg-cyan/10 px-3.5 py-2.5 text-xs text-cyan">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <p>
            {liveState.status === 'recording'
              ? 'Audio is being captured from your selected meeting tab. Do not close the meeting tab while recording.'
              : 'Open your meeting first, then click "Start Live Capture", select the meeting tab, and enable "Share tab audio".'}
          </p>
        </div>

        <Button
          type="submit"
          variant="primary"
          size="lg"
          fullWidth
          isLoading={isSubmitting}
        >
          {liveState.status === 'recording' ? 'Stop & Join Class' : 'Join Class'}
        </Button>
      </form>
    </Card>
  )
}


