// -----------------------------------------------------------------------------
// Mock service layer.
//
// Every function here simulates a network call with a short delay and returns
// data from `src/data/mockData.ts`. This is what currently powers the app.
// Swap `classService.ts` over to `api.ts` once the real backend exists —
// no page or component needs to change.
// -----------------------------------------------------------------------------

import { demoStudent, mockAnnouncements, mockClasses, mockNotes, processingStages } from '@/data/mockData'
import type { Announcement, ClassSession, DashboardSummary, LectureNote, ProcessingStage, Student } from '@/types'
import { sleep } from '@/lib/utils'

export async function mockLogin(email: string, _password: string): Promise<Student> {
  await sleep(700)
  return { ...demoStudent, email: email || demoStudent.email }
}

export async function mockSignUp(name: string, email: string, _password: string): Promise<Student> {
  await sleep(800)
  const initials = name
    .split(' ')
    .map((p) => p[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
  return { ...demoStudent, name, email, avatarInitials: initials || 'ST' }
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  await sleep(300)
  return {
    totalClasses: mockClasses.length,
    classesAttended: mockClasses.filter((c) => c.status === 'completed').length,
    notesGenerated: mockNotes.length,
    importantAnnouncements: mockAnnouncements.length,
  }
}

export async function getPreviousClasses(): Promise<ClassSession[]> {
  await sleep(350)
  return [...mockClasses].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
}

export async function getClassById(id: string): Promise<ClassSession | undefined> {
  await sleep(200)
  return mockClasses.find((c) => c.id === id)
}

export async function getRecentClasses(limit = 3): Promise<ClassSession[]> {
  const all = await getPreviousClasses()
  return all.filter((c) => c.status === 'completed').slice(0, limit)
}

export async function getAllNotes(): Promise<LectureNote[]> {
  await sleep(350)
  return [...mockNotes].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
}

export async function getRecentNotes(limit = 3): Promise<LectureNote[]> {
  const all = await getAllNotes()
  return all.slice(0, limit)
}

export async function getNoteByClassId(classId: string): Promise<LectureNote | undefined> {
  await sleep(250)
  return mockNotes.find((n) => n.classId === classId)
}

export async function getAllAnnouncements(): Promise<Announcement[]> {
  await sleep(300)
  return [...mockAnnouncements].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
}

export async function getRecentAnnouncements(limit = 4): Promise<Announcement[]> {
  const all = await getAllAnnouncements()
  return all.slice(0, limit)
}

export async function getAnnouncementsForClass(classId: string): Promise<Announcement[]> {
  await sleep(200)
  return mockAnnouncements.filter((a) => a.relatedClassId === classId)
}

export function getProcessingStages(): ProcessingStage[] {
  return processingStages
}

/**
 * Simulates joining/starting a demo session. Returns a synthetic class id so
 * the processing + results pages have something to key off of. This does NOT
 * connect to any real meeting provider.
 */
export async function startDemoSession(title: string, subject: string): Promise<ClassSession> {
  await sleep(500)
  return {
    id: `demo-${Date.now()}`,
    title: title || 'Untitled Class',
    subject: subject || 'General',
    date: new Date().toISOString(),
    status: 'live',
    hasNotes: false,
  }
}

/**
 * Builds placeholder notes for a freshly-started demo session (one with no
 * pre-seeded mock data). Clearly generic — nothing here is inferred from real
 * audio, since no real transcription/analysis has occurred.
 */
export async function generateDemoNote(session: ClassSession): Promise<LectureNote> {
  await sleep(250)
  return {
    id: `note-${session.id}`,
    classId: session.id,
    title: session.title || 'Untitled Class',
    subject: session.subject || 'General',
    date: session.date,
    preview: 'Demo output — once the Deep Learning backend is connected, this preview will summarize what was actually said.',
    summary:
      'This is placeholder summary text. In the connected version, the DL backend will transcribe the session audio and generate a real summary of what was covered.',
    topics: ['Sample topic A', 'Sample topic B', 'Sample topic C'],
    sections: [
      {
        heading: 'Demo Section',
        points: [
          'This is placeholder note content shown because no real audio/transcript was processed.',
          'Connect the backend described in services/api.ts to replace this with real generated notes.',
        ],
      },
    ],
  }
}

/** Builds a single placeholder announcement for a freshly-started demo session. */
export async function generateDemoAnnouncements(session: ClassSession): Promise<Announcement[]> {
  await sleep(200)
  return [
    {
      id: `ann-${session.id}-demo`,
      text: 'This is a placeholder announcement shown for demo purposes. Real announcements will be extracted from lecture audio once the backend is connected.',
      category: 'General Announcement',
      relatedLecture: session.title || 'Untitled Class',
      relatedClassId: session.id,
      date: session.date,
    },
  ]
}
