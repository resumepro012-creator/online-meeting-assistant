import { useRef, useState, useEffect, type FormEvent } from 'react'
import { Video, Link2, BookMarked, Upload, FileAudio, Info, ShieldAlert, Bot } from 'lucide-react'
import { Input } from '@/components/common/Input'
import { Button } from '@/components/common/Button'
import { Card } from '@/components/common/Card'
import { cn } from '@/lib/utils'
import * as classService from '@/services/classService'
import type { MeetingPolicy, BotStatus } from '@/services/classService'

interface JoinClassFormProps {
  onJoin: (data: { title: string; subject: string; meetingLink: string; file: File | null }) => void
  /**
   * Called once the assistant has actually been admitted to the meeting. The
   * page creates the class and starts recording the meeting audio, then shows
   * the live session view. Resolves with an error message, or null on success.
   */
  onStartBotSession: (data: {
    title: string
    subject: string
    meetingLink: string
  }) => Promise<string | null>
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

export function JoinClassForm({ onJoin, onStartBotSession, isSubmitting }: JoinClassFormProps) {
  const [title, setTitle] = useState('')
  const [subject, setSubject] = useState('')
  const [meetingLink, setMeetingLink] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [policy, setPolicy] = useState<MeetingPolicy | null>(null)
  const [botStatus, setBotStatus] = useState<BotStatus | null>(null)
  const [botBusy, setBotBusy] = useState(false)
  const [botError, setBotError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const botPollRef = useRef<number | null>(null)
  // Guards against starting the same bot session twice while polling.
  const botStartTriggeredRef = useRef(false)
  // Latest form values, so the 3s polling callback never uses stale input.
  const formValuesRef = useRef({ title, subject, meetingLink })

  // The assistant bot counts as a capture method: once it has been started the
  // student can begin the class without uploading a file, and the backend will
  // record the meeting audio and generate the notes when the class ends.
  const botActive =
    !!botStatus?.found &&
    botStatus.status !== 'failed' &&
    botStatus.status !== 'stopped' &&
    botStatus.status !== 'unsupported'

  useEffect(() => {
    return () => {
      if (botPollRef.current) window.clearInterval(botPollRef.current)
    }
  }, [])

  useEffect(() => {
    formValuesRef.current = { title, subject, meetingLink }
  }, [title, subject, meetingLink])

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

        // The moment the host admits the assistant, the class really begins:
        // the page creates the class and starts recording the meeting audio,
        // so ending the session yields notes, summary and class history.
        if (status.status === 'admitted' && !botStartTriggeredRef.current) {
          botStartTriggeredRef.current = true
          stopBotPolling()
          const values = formValuesRef.current
          const error = await onStartBotSession({
            title: values.title.trim(),
            subject: values.subject.trim(),
            meetingLink: link,
          })
          if (error) {
            setBotError(error)
            botStartTriggeredRef.current = false
          }
          return
        }

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
    // The assistant starts the class for real once admitted, so the title and
    // subject are required before it is launched.
    if (!title.trim()) {
      setErrors((prev) => ({ ...prev, title: 'Class title is required.' }))
      return
    }
    if (!subject.trim()) {
      setErrors((prev) => ({ ...prev, subject: 'Subject is required.' }))
      return
    }
    botStartTriggeredRef.current = false
    setErrors((prev) => ({ ...prev, title: '', subject: '' }))
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
    botStartTriggeredRef.current = false
    try {
      await classService.stopMeetingBot(link)
    } catch {
      // Ignore — we still clear the local state.
    }
    setBotStatus(null)
    setBotError(null)
  }

  const validate = () => {
    const next: Record<string, string> = {}
    if (!title.trim()) next.title = 'Class title is required.'
    if (!subject.trim()) next.subject = 'Subject is required.'
    if (!file && !botActive) {
      next.session =
        'Upload a recording or join with the assistant bot.'
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

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()

    if (!validate()) return

    onJoin({
      title,
      subject,
      meetingLink,
      file,
    })
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
              Tip: Use "Join with Assistant Bot" for live classes, or "Upload File" for a previously recorded lecture.
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
                  The assistant opens the meeting in its own browser window and requests
                  admission. Once the host admits it, the class starts and the meeting audio
                  is recorded automatically — end the session to get the notes and summary.
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
          or upload a recording
          <span className="h-px flex-1 bg-card-border" />
        </div>

        <div>
          <p className="mb-1.5 text-sm font-medium text-white/85">Upload File</p>
          {!file ? (
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex w-full flex-col items-center gap-2 rounded-xl border border-dashed border-card-border bg-card/40 px-4 py-6 text-center transition-colors hover:border-primary/50"
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

        <input
          ref={fileInputRef}
          type="file"
          accept="audio/*,.txt,.vtt,.srt"
          className="hidden"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />

        {errors.session && <p className="text-xs text-red-400">{errors.session}</p>}

        <div className="flex items-start gap-2 rounded-xl border border-cyan/25 bg-cyan/10 px-3.5 py-2.5 text-xs text-cyan">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <p>
            The assistant bot captures the meeting audio automatically. Use "Upload File" for
            a previously recorded lecture or transcript.
          </p>
        </div>

        <Button
          type="submit"
          variant="primary"
          size="lg"
          fullWidth
          isLoading={isSubmitting}
        >
          Join Class
        </Button>
      </form>
    </Card>
  )
}
