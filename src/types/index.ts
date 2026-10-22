// ---------- Auth ----------
export interface Student {
  id: string
  name: string
  email: string
  avatarInitials: string
  program?: string
}

// ---------- Classes ----------
export type ClassStatus = 'upcoming' | 'live' | 'completed' | 'processing'

export interface ClassSession {
  id: string
  title: string
  subject: string
  date: string // ISO
  durationMinutes?: number
  status: ClassStatus
  meetingLink?: string
  hasNotes: boolean
}

// ---------- Notes ----------
export interface LectureNote {
  id: string
  classId: string
  title: string
  subject: string
  date: string // ISO
  preview: string
  summary: string
  topics: string[]
  sections: NoteSection[]
}

export interface NoteSection {
  heading: string
  points: string[]
}

// ---------- Announcements ----------
export type AnnouncementCategory =
  | 'Assignment'
  | 'Quiz'
  | 'Exam'
  | 'Deadline'
  | 'Schedule Change'
  | 'General Announcement'

export interface Announcement {
  id: string
  text: string
  category: AnnouncementCategory
  relatedLecture: string
  relatedClassId: string
  date: string // ISO
  deadline?: string // ISO, only if explicitly available
}

// ---------- Processing ----------
export type ProcessingStageKey =
  | 'preparing'
  | 'transcribing'
  | 'analyzing'
  | 'identifying'
  | 'extracting'
  | 'generating'

export interface ProcessingStage {
  key: ProcessingStageKey
  label: string
}

// ---------- Dashboard ----------
export interface DashboardSummary {
  totalClasses: number
  classesAttended: number
  notesGenerated: number
  importantAnnouncements: number
}
