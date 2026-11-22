import { useRef, useState, useEffect, type FormEvent } from 'react'
import { Video, Link2, BookMarked, Upload, FileAudio, X, Info, ShieldAlert, Mic, StopCircle, Bot } from 'lucide-react'
import { Input } from '@/components/common/Input'
import { Button } from '@/components/common/Button'
import { Card } from '@/components/common/Card'
import { cn } from '@/lib/utils'
import * as classService from '@/services/classService'
import type { MeetingPolicy, BotStatus } from '@/services/classService'
import { LiveAudioService, type LiveAudioState } from '@/services/LiveAudioService'

interface JoinClassFormProps {
  onJoin: (data: { title: string; subject: string; meetingLink: string; file: File | null }) => void
  isSubmitting: boolean
}

const BOT_TERMINAL_STATUSES = ['admitted', 'failed', 'stopped', 'unsupported']

function describeBotStatus(status: string | null): { label: string; tone: string } {
  switch (status) {
    case 'starting':
    case 'opening':
      return { label: 'Opening the meeting…', tone: 'text-cyan' }
    case 'action_required':
      return { label: 'Action needed in the assistant window', tone: 'text-amber-300' }
    case 'requesting_admission':
      return { label: 'Requesting permission to enter…', tone: 'text-amber-300' }
    case 'waiting_for_host':
      return { label: 'Waiting for the host to admit the assistant…', tone: 'text-amber-300' }
    case 'admitted':
      return { label: 'Assistant admitted to the meeting', tone: 'text-emerald-400' }
    case 'failed':
      return { label: 'Assistant could not join', tone: 'text-red-400' }
    case 'stopped':
      return { label: 'Assistant left the meeting', tone: 'text-muted' }
    default:
      return { label: 'Assistant is working…', tone: 'text-muted' }
  }
}

export function JoinClassForm({ onJoin, isSubmitting }: JoinClassFormProps) {
  const [title, setTitle] = useState('')
  const [subject, setSubject] = useState('')
  const [meetingLink, setMeetingLink] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [policy, setPolicy] = useState<MeetingPolicy | null>(null)
  const [liveState, setLiveState] = useState<LiveAudioState>({ status: 'idle', durationSeconds: 0 })
  const [botStatus, setBotStatus] = useState<BotStatus | null>(null)
  const [botBusy, setBotBusy] = useState(false)
  const [botError, setBotError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const liveServiceRef = useRef<LiveAudioService | null>(null)
  const botPollRef = useRef<number | null>(null)

  // The assistant bot counts as a capture method: once it has been started the
  // student can begin the class without uploading a file, and the backend will
  // record the meeting audio and generate the notes when the class ends.
  const botActive =
    !!botStatus?.found &&
    botStatus.status !== 'failed' &&
    botStatus.status !== 'stopped' &&
    botStatus.status !== 'unsupported'

  useEffect(() => {
    liveServiceRef.current = new LiveAudioService(setLiveState)

    return () => {
      void liveServiceRef.current?.stop()
      if (botPollRef.current) window.clearInterval(botPollRef.current)
    }
  }, [])

  const stopBotPolling = () => {
    if (botPollRef.current !== null) {
      window.clearInterval(botPollRef.current)
      botPollRef.current = null
    }
  }

  const startBotPolling = (link: string) => {
    stopBotPolling()
    botPollRef.current = window.setInterval(async () => {
      try {
        const status = await classService.getBotStatus(link)
        if (!status.found) {
          stopBotPolling()
          return
        }
        setBotStatus(status)
        if (status.status && BOT_TERMINAL_STATUSES.includes(status.status)) {
          stopBotPolling()
        }
      } catch {
        // Transient network error — keep polling.
      }
    }, 3000)
  }

  const handleJoinBot = async () => {
    const link = meetingLink.trim()
    if (!link) {
      setBotError('Paste the meeting link first.')
      return
    }
    setBotBusy(true)
    setBotError(null)
    try {
      const result = await classService.joinMeetingAsBot(link)
      if (!result.botId) {
        setBotStatus(null)
        setBotError(result.detail)
        return
      }
      setBotStatus({
        found: true,
        botId: result.botId,
        link,
        status: result.status,
        detail: result.detail,
        startedAt: null,
        updatedAt: null,
      })
      startBotPolling(link)
    } catch (e) {
      setBotError(e instanceof Error ? e.message : 'Could not start the assistant bot.')
    } finally {
      setBotBusy(false)
    }
  }

  const handleStopBot = async () => {
    const link = meetingLink.trim()
    stopBotPolling()
    try {
      await classService.stopMeetingBot(link)
    } catch {
      // Ignore — we still clear the local state.
    }
    setBotStatus(null)
    setBotError(null)
  }

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
    if (!file && liveState.status !== 'recording' && !botActive) {
      next.session =
        'Upload a recording, start a live capture, or join with the assistant bot.'
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
              {policy.automatedJoinSupported
                ? 'Use "Join with Assistant Bot" below — the assistant opens the meeting and asks the host to admit it.'
                : 'Join this meeting yourself with your institute account, then upload the authorized recording.'}
            </p>
            {policy.accessControls.length > 0 && (
              <ul className="mt-2 list-disc space-y-0.5 pl-4 text-muted">
                {policy.accessControls.map((control) => (
                  <li key={control}>{control}</li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-cyan">
              Tip: For live capture, first join in your browser and enable "Share tab audio".
            </p>
          </div>
        )}

        <div className="rounded-xl border border-primary/30 bg-primary/5 px-3.5 py-3">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-start gap-2">
              <Bot className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              <div>
                <p className="text-sm font-medium text-white">Join with Assistant Bot</p>
                <p className="mt-0.5 text-xs text-muted">
                  The assistant opens the meeting in its own browser window, requests
                  admission, then records the class so notes are generated when you end the session.
                </p>
              </div>
            </div>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={handleJoinBot}
              isLoading={botBusy}
              disabled={!meetingLink.trim()}
              className="shrink-0"
            >
              Join
            </Button>
          </div>

          {botStatus && (
            <div className="mt-2.5 flex items-start justify-between gap-3 rounded-lg border border-card-border bg-card/60 px-3 py-2">
              <div>
                <p className={cn('text-xs font-medium', describeBotStatus(botStatus.status).tone)}>
                  {describeBotStatus(botStatus.status).label}
                </p>
                {botStatus.detail && (
                  <p className="mt-0.5 text-[11px] text-muted">{botStatus.detail}</p>
                )}
              </div>
              <button
                type="button"
                onClick={handleStopBot}
                className="shrink-0 text-xs text-muted underline underline-offset-2 hover:text-white"
              >
                Leave
              </button>
            </div>
          )}

          {botError && (
            <p className="mt-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
              {botError}
            </p>
          )}
        </div>

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
