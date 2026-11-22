// -----------------------------------------------------------------------------
// Real API service layer.
//
// This file is the ONLY place that knows how to talk to the FastAPI backend in
// `backend/`. `classService.ts` re-exports everything below, so pages keep
// importing from `@/services/classService` exactly as before.
//
// Every function returns the same shapes declared in `src/types/index.ts`
// (the backend serialises to camelCase on purpose), so no component needed to
// be rewritten when mock data was replaced with real responses.
// -----------------------------------------------------------------------------

import type {
  Announcement,
  ClassSession,
  ClassStatus,
  DashboardSummary,
  LectureNote,
  ProcessingStage,
  Student,
} from '@/types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

const TOKEN_KEY = 'ai-class-assistant.token'

// --------------------------------------------------------------------------- //
// Access-token storage
// --------------------------------------------------------------------------- //
let accessToken: string | null = (() => {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
})()

export function setAccessToken(token: string | null) {
  accessToken = token
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // sessionStorage unavailable — the token just won't survive a page reload
  }
}

export function hasAccessToken(): boolean {
  return !!accessToken
}

// --------------------------------------------------------------------------- //
// Fetch wrapper
// --------------------------------------------------------------------------- //
/** Machine-readable error codes the backend sends alongside its messages. */
export type ApiErrorCode =
  | 'email_domain_not_allowed'
  | 'email_already_registered'
  | 'email_not_verified'
  | 'invalid_credentials'
  | 'invalid_code'
  | 'code_expired'
  | 'too_many_attempts'
  | 'resend_too_soon'
  | 'invalid_reset_token'
  | 'verification_email_failed'
  | 'unauthorized'
  | string

export class ApiError extends Error {
  status: number
  code: ApiErrorCode | null

  constructor(status: number, message: string, code: ApiErrorCode | null = null) {
    super(message)
    this.status = status
    this.code = code
    this.name = 'ApiError'
  }
}

/** Turns any FastAPI error payload into one readable sentence. */
function describeError(status: number, body: unknown, statusText: string): ApiError {
  if (body && typeof body === 'object') {
    const detail = (body as { detail?: unknown }).detail
    // Our own endpoints raise HTTPException(detail={"code": ..., "message": ...})
    if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
      const { code, message } = detail as { code?: string; message?: string }
      return new ApiError(status, message ?? 'Request failed.', code ?? null)
    }
    if (typeof detail === 'string') return new ApiError(status, detail)
    // FastAPI's 422 validation payload
    if (Array.isArray(detail)) {
      const first = detail[0] as { msg?: string; loc?: unknown[] } | undefined
      if (first?.msg) {
        const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : undefined
        return new ApiError(status, field ? `${String(field)}: ${first.msg}` : first.msg)
      }
    }
  }
  if (status === 401) return new ApiError(status, 'Your session has expired. Please sign in again.')
  if (status === 403) return new ApiError(status, 'You are not allowed to view this resource.')
  if (status === 404) return new ApiError(status, 'That resource was not found.')
  if (status >= 500) return new ApiError(status, 'The server hit an unexpected error. Check the backend logs.')
  return new ApiError(status, `Request failed (${status} ${statusText}).`)
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const isFormData = options.body instanceof FormData
  if (!isFormData && options.body) headers.set('Content-Type', 'application/json')
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)

  let res: Response
  try {
    res = await fetch(`${BASE_URL}${path}`, { ...options, headers })
  } catch {
    throw new ApiError(
      0,
      `Cannot reach the backend at ${BASE_URL}. Start it with: cd backend && .venv\\Scripts\\python.exe -m uvicorn app.main:app --reload`
    )
  }

  if (!res.ok) {
    let body: unknown = null
    try {
      body = await res.json()
    } catch {
      // non-JSON error body (e.g. a proxy error page) — fall through
    }
    throw describeError(res.status, body, res.statusText)
  }

  if (res.status === 204) return undefined as T
  const text = await res.text()
  return (text ? JSON.parse(text) : undefined) as T
}

// --------------------------------------------------------------------------- //
// Wire types (mirror `backend/app/schemas/__init__.py`)
// --------------------------------------------------------------------------- //
interface AuthResponseWire {
  accessToken: string
  tokenType: string
  expiresIn: number
  student: Student
}

export interface RegisterResult {
  email: string
  verificationRequired: boolean
  message: string
  /** Present only while the backend uses the development `console` email backend. */
  devVerificationCode?: string | null
}

export interface ResendVerificationResult {
  message: string
  devVerificationCode?: string | null
}

export interface AuthPolicy {
  allowedEmailDomains: string[]
  universityEmailDomains: string[]
  /** When true the backend also accepts any `.edu` / `.edu.<cc>` / `.ac.<cc>` address. */
  acceptAnyAcademicDomain: boolean
  verificationRequired: boolean
  verificationCodeLength: number
  resendCooldownSeconds: number
  devCodeExposed: boolean
}

interface CourseWire {
  id: string
  title: string
  subject: string
  date: string
  durationMinutes?: number | null
  status: string
  meetingLink?: string | null
  hasNotes: boolean
}

export interface Lecture {
  id: string
  courseId: string
  sourceType: string
  originalFilename?: string | null
  status: string
  durationSeconds?: number | null
  errorMessage?: string | null
  createdAt?: string | null
  completedAt?: string | null
}

export interface JobStatus {
  jobId: string
  lectureId: string
  courseId: string
  status: string
  stage: string
  progress: number
  message?: string | null
  error?: string | null
  stages: ProcessingStage[]
}

export interface LectureCreated {
  lecture: Lecture
  job: JobStatus
}

export interface PipelineHealth {
  status: string
  database: string
  pipeline: {
    speechToText: { available: boolean; backend: string; model: string | null; note: string }
    segmentClassifier: {
      method: string
      isRealModel: boolean
      transformersInstalled: boolean
      backend: string
    }
    summarizer: { backend: string }
  }
}

export interface ClassResults {
  courseId: string
  lectureId?: string
  note?: LectureNote | null
  announcements: Announcement[]
  questions: { id: string; text: string; speaker?: string | null; sourceSeconds?: number | null }[]
  actionItems?: { id: string; kind: string; text: string; dueAt?: string | null }[]
  [key: string]: unknown
}

const toClassSession = (course: CourseWire): ClassSession => ({
  id: course.id,
  title: course.title,
  subject: course.subject,
  date: course.date,
  durationMinutes: course.durationMinutes ?? undefined,
  status: course.status as ClassStatus,
  meetingLink: course.meetingLink ?? undefined,
  hasNotes: course.hasNotes,
})

// --------------------------------------------------------------------------- //
// Auth
// --------------------------------------------------------------------------- //
export interface StartSessionInput {
  title: string
  subject: string
  meetingLink?: string
  file?: File | null
}

export interface StartedSession {
  session: ClassSession
  lectureId: string | null
  /** True when the backend is capturing the meeting's audio for this class. */
  recordingStarted: boolean
}

/**
 * Creates the class. When a recording was provided it is uploaded and queued for
 * processing; otherwise the backend starts capturing the meeting's system audio,
 * which is turned into a lecture when the student ends the session.
 */
export async function startSession(input: StartSessionInput): Promise<StartedSession> {
  const course = await request<CourseWire>('/classes', {
    method: 'POST',
    body: JSON.stringify({
      title: input.title,
      subject: input.subject,
      meetingLink: input.meetingLink || null,
    }),
  })

  let lectureId: string | null = null
  let recordingStarted = false

  if (input.file) {
    const form = new FormData()
    form.append('courseId', course.id)
    form.append('file', input.file)
    form.append('startProcessing', 'true')
    const created = await request<LectureCreated>('/lectures', { method: 'POST', body: form })
    lectureId = created.lecture.id
  } else {
    // No file was supplied: the assistant records the meeting audio on this
    // machine and the lecture is built from it when the class ends.
    try {
      await startMeetingRecording(course.id)
      recordingStarted = true
    } catch (err) {
      const detail = err instanceof ApiError ? err.message : 'Unknown error.'
      throw new ApiError(
        0,
        `Could not start recording this class on this computer (${detail}). ` +
          'Use "Upload File" or "Start Live Capture" instead.'
      )
    }
  }

  return { session: toClassSession(course), lectureId, recordingStarted }
}

/** Exchanges an institute email + password for an access token. */
export async function login(email: string, password: string): Promise<Student> {
  const result = await request<AuthResponseWire>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
  setAccessToken(result.accessToken)
  return result.student
}

/**
 * Creates an **inactive** account and asks the backend to email a verification
 * code. No token is issued here — the account cannot sign in until the code has
 * been confirmed via `verifyEmail`.
 */
export async function signUp(
  name: string,
  email: string,
  password: string,
  program?: string
): Promise<RegisterResult> {
  return request<RegisterResult>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ name, email, password, program: program || null }),
  })
}

/** Confirms the emailed code; only then does the backend issue a token. */
export async function verifyEmail(email: string, code: string): Promise<Student> {
  const result = await request<AuthResponseWire>('/auth/verify-email', {
    method: 'POST',
    body: JSON.stringify({ email, code }),
  })
  setAccessToken(result.accessToken)
  return result.student
}

export function resendVerificationCode(email: string): Promise<ResendVerificationResult> {
  return request<ResendVerificationResult>('/auth/resend-verification', {
    method: 'POST',
    body: JSON.stringify({ email }),
  })
}

/** Always resolves with the same generic message, to avoid account enumeration. */
export async function forgotPassword(email: string): Promise<string> {
  const result = await request<{ message: string }>('/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify({ email }),
  })
  return result.message
}

export async function resetPassword(token: string, password: string): Promise<string> {
  const result = await request<{ message: string }>('/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify({ token, password }),
  })
  return result.message
}

/** Approved university domains, straight from the backend — never hardcoded. */
export function getAuthPolicy(): Promise<AuthPolicy> {
  return request<AuthPolicy>('/auth/policy')
}

/**
 * Institutional addresses end in `.edu` (including `.edu.pk`, `.edu.au`) or
 * `.ac.<cc>` (e.g. `.ac.uk`). Anchored to the end, so `edu.gmail.com` is not a
 * match. Mirrors the backend's `is_academic_email_domain`.
 */
const ACADEMIC_DOMAIN_PATTERN = /\.edu(\.[a-z]{2,3})?$|\.ac\.[a-z]{2,3}$/

/**
 * Client-side mirror of the backend's domain rule: an explicitly approved
 * domain (or a subdomain of one, e.g. `cs.student.edu`), or — when the policy
 * allows it — any institutional `.edu` / `.ac.<cc>` address.
 *
 * The backend remains the authority — `POST /auth/login` re-checks the domain
 * itself. This only lets the form answer instantly instead of waiting for a
 * round trip.
 */
export function isAllowedUniversityEmail(email: string, policy: AuthPolicy | null): boolean {
  const parts = email.trim().toLowerCase().split('@')
  if (parts.length !== 2 || !parts[0] || !parts[1]) return false
  const domain = parts[1]
  const approved = policy?.allowedEmailDomains ?? []
  if (approved.some((allowed) => domain === allowed || domain.endsWith(`.${allowed}`))) {
    return true
  }
  return !!policy?.acceptAnyAcademicDomain && ACADEMIC_DOMAIN_PATTERN.test(domain)
}

export function getCurrentStudent(): Promise<Student> {
  return request<Student>('/auth/me')
}

export function logout() {
  setAccessToken(null)
}

// --------------------------------------------------------------------------- //
// Classes, lectures and generated outputs
// --------------------------------------------------------------------------- //
export async function getPreviousClasses(): Promise<ClassSession[]> {
  const courses = await request<CourseWire[]>('/classes')
  return courses.map(toClassSession)
}

export async function getClassById(classId: string): Promise<ClassSession> {
  return toClassSession(await request<CourseWire>(`/classes/${classId}`))
}

export function getRecentClasses(limit = 3): Promise<ClassSession[]> {
  return request<CourseWire[]>(`/dashboard/recent-classes?limit=${limit}`).then((courses) =>
    courses.map(toClassSession)
  )
}

export async function listClassLectures(classId: string): Promise<Lecture[]> {
  return request<Lecture[]>(`/classes/${classId}/lectures`)
}

export async function startProcessing(lectureId: string): Promise<LectureCreated> {
  return request<LectureCreated>(`/lectures/${lectureId}/process`, { method: 'POST' })
}

export function getJobStatus(lectureId: string): Promise<JobStatus> {
  return request<JobStatus>(`/lectures/${lectureId}/status`)
}

export function getLectureResults(lectureId: string): Promise<ClassResults> {
  return request<ClassResults>(`/lectures/${lectureId}/results`)
}

export function getClassResults(classId: string): Promise<ClassResults> {
  return request<ClassResults>(`/classes/${classId}/results`)
}

/** Alias kept because the pages still import this name. */
export const getResultsForClass = getClassResults

export function getNoteByClassId(classId: string): Promise<LectureNote> {
  return request<LectureNote>(`/classes/${classId}/notes`)
}

export function getAnnouncementsForClass(classId: string): Promise<Announcement[]> {
  return request<Announcement[]>(`/classes/${classId}/announcements`)
}

export function getAllAnnouncements(): Promise<Announcement[]> {
  return request<Announcement[]>('/announcements')
}

export async function getRecentAnnouncements(limit = 4): Promise<Announcement[]> {
  const all = await getAllAnnouncements()
  return all.slice(0, limit)
}

export function getAllNotes(): Promise<LectureNote[]> {
  return request<LectureNote[]>('/notes')
}

export async function getRecentNotes(limit = 3): Promise<LectureNote[]> {
  const all = await getAllNotes()
  return all.slice(0, limit)
}

export function getDashboardSummary(): Promise<DashboardSummary> {
  return request<DashboardSummary>('/dashboard/summary')
}

export function getPipelineHealth(): Promise<PipelineHealth> {
  return request<PipelineHealth>('/health')
}

// --------------------------------------------------------------------------- //
// Meeting access policy
// --------------------------------------------------------------------------- //
/**
 * What the meeting platform allows. Signing in here is *not* the same as being
 * authorized to join someone else's meeting, so the backend reports the
 * platform's access controls and the permitted alternative instead of joining.
 */
export interface MeetingPolicy {
  providedLink: string | null
  linkRecognised: boolean
  platform: string
  platformName: string
  applicationAuthenticationRequired: boolean
  meetingAuthorizationRequired: boolean
  automatedJoinSupported: boolean
  officialApiAvailable: boolean
  apiNote: string
  accessControls: string[]
  permittedAlternative: string
  policy: string
  liveCaptureImplemented: boolean
  supportedInput: string[]
}

export function getMeetingPolicy(link?: string): Promise<MeetingPolicy> {
  const query = link ? `?link=${encodeURIComponent(link)}` : ''
  return request<MeetingPolicy>(`/meetings/policy${query}`)
}

/** Result of asking the assistant bot to join. `botId` is null when the
 * platform does not support automated joining. */
export interface BotJoinResult {
  botId: string | null
  status: string
  detail: string
}

/** Live state of the assistant bot for a meeting link. */
export interface BotStatus {
  found: boolean
  botId: string | null
  link: string | null
  status: string | null
  detail: string | null
  startedAt: string | null
  updatedAt: string | null
}

export function joinMeetingAsBot(link: string): Promise<BotJoinResult> {
  return request<BotJoinResult>(`/meetings/join?link=${encodeURIComponent(link)}`, {
    method: 'POST',
  })
}

export function getBotStatus(link: string): Promise<BotStatus> {
  return request<BotStatus>(`/meetings/bot/status?link=${encodeURIComponent(link)}`)
}

export function stopMeetingBot(link: string): Promise<{ message: string }> {
  return request<{ message: string }>(`/meetings/bot/stop?link=${encodeURIComponent(link)}`, {
    method: 'POST',
  })
}

/**
 * Starts capturing the meeting's system audio for a class. The assistant bot
 * plays the meeting through the machine's speakers, so the captured audio is
 * what the class actually sounded like.
 */
export async function startMeetingRecording(courseId: string): Promise<void> {
  await request<{ message: string }>(
    `/meetings/recording/start?course_id=${encodeURIComponent(courseId)}`,
    { method: 'POST' }
  )
}

/**
 * Stops the capture, turns the WAV into a lecture and queues it for processing.
 * Returns the new lecture id that the Processing page polls.
 */
export async function stopMeetingRecording(): Promise<{ lectureId: string; courseId: string }> {
  const created = await request<LectureCreated>('/meetings/recording/stop', { method: 'POST' })
  return { lectureId: created.lecture.id, courseId: created.lecture.courseId }
}

// --------------------------------------------------------------------------- //
// Processing stepper
// --------------------------------------------------------------------------- //
/**
 * The stage list is a fixed part of the pipeline contract (see
 * `backend/app/ml/stages.py`); the live job status only tells us which one is
 * currently active, so this stays synchronous like the mock version was.
 */
export function getProcessingStages(): ProcessingStage[] {
  return [
    { key: 'preparing', label: 'Preparing lecture content' },
    { key: 'transcribing', label: 'Transcribing audio' },
    { key: 'analyzing', label: 'Analyzing lecture content' },
    { key: 'identifying', label: 'Identifying important concepts' },
    { key: 'extracting', label: 'Extracting announcements' },
    { key: 'generating', label: 'Generating lecture notes' },
  ] as ProcessingStage[]
}
