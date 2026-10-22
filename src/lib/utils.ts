import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
}

export function initials(name: string): string {
  return name
    .split(' ')
    .map((p) => p[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

import type { LectureNote } from '@/types'

export function noteToMarkdown(note: LectureNote): string {
  const lines = [
    `# ${note.title}`,
    `*${note.subject} — ${formatDate(note.date)}*`,
    '',
    '## Summary',
    note.summary,
    '',
    '## Important Topics',
    ...note.topics.map((t) => `- ${t}`),
    '',
    '## Notes',
    ...note.sections.flatMap((s) => [`### ${s.heading}`, ...s.points.map((p) => `- ${p}`), '']),
  ]
  return lines.join('\n')
}

export function downloadNoteAsMarkdown(note: LectureNote) {
  const blob = new Blob([noteToMarkdown(note)], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${note.title.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}-notes.md`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
