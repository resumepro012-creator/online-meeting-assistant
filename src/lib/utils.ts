import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { Announcement, ClassResults, LectureNote } from '@/types'

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

function escapeHtml(text: string): string {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

export function downloadClassSummaryAsPdf(results: ClassResults, sessionTitle: string, sessionSubject: string) {
  const sections: string[] = []

  sections.push(`
    <div class="header">
      <h1>${escapeHtml(sessionTitle)}</h1>
      <div class="subject">${escapeHtml(sessionSubject)}</div>
      <hr>
    </div>
  `)

  if (results.note) {
    sections.push(`<h2>Lecture Summary</h2><p>${escapeHtml(results.note.summary)}</p>`)

    if (results.note.topics.length) {
      sections.push(`<h2>Important Topics</h2><p>${results.note.topics.map(escapeHtml).join('  •  ')}</p>`)
    }

    if (results.note.sections.length) {
      const notesHtml = results.note.sections
        .map(
          (s) => `
            <div class="section">
              <h3>${escapeHtml(s.heading)}</h3>
              <ul>${s.points.map((p) => `<li>${escapeHtml(p)}</li>`).join('')}</ul>
            </div>
          `
        )
        .join('')
      sections.push(`<h2>Lecture Notes</h2>${notesHtml}`)
    }
  }

  const announcementGroups: { heading: string; items: Announcement[] }[] = [
    { heading: 'Assignments', items: results.announcements.filter((a) => a.category === 'Assignment') },
    { heading: 'Quizzes', items: results.announcements.filter((a) => a.category === 'Quiz') },
    { heading: 'Exams', items: results.announcements.filter((a) => a.category === 'Exam') },
    { heading: 'Deadlines', items: results.announcements.filter((a) => a.category === 'Deadline') },
    { heading: 'Schedule Changes', items: results.announcements.filter((a) => a.category === 'Schedule Change') },
    { heading: 'General Announcements', items: results.announcements.filter((a) => a.category === 'General Announcement') },
  ]

  for (const group of announcementGroups) {
    if (!group.items.length) continue
    const itemsHtml = group.items
      .map((a) => {
        let text = a.text
        if (a.deadline) text += `  (Due: ${formatDate(a.deadline)})`
        else if (a.deadlineText) text += `  (Due: ${a.deadlineText})`
        return `<li>${escapeHtml(text)}</li>`
      })
      .join('')
    sections.push(`<h2>${group.heading}</h2><ul>${itemsHtml}</ul>`)
  }

  if (results.questions && results.questions.length) {
    const itemsHtml = results.questions
      .map((q) => {
        const prefix = q.speaker ? `[${q.speaker}] ` : ''
        return `<li>${escapeHtml(prefix + q.text)}</li>`
      })
      .join('')
    sections.push(`<h2>Questions Raised</h2><ul>${itemsHtml}</ul>`)
  }

  if (results.actionItems && results.actionItems.length) {
    const itemsHtml = results.actionItems
      .map((item) => {
        let text = item.text
        if (item.assignee) text = `[${item.assignee}] ${text}`
        if (item.dueAt) text += `  (Due: ${formatDate(item.dueAt)})`
        else if (item.dueText) text += `  (Due: ${item.dueText})`
        return `<li>${escapeHtml(text)}</li>`
      })
      .join('')
    sections.push(`<h2>Action Items</h2><ul>${itemsHtml}</ul>`)
  }

  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>${escapeHtml(sessionTitle)} - Summary</title>
  <style>
    @page { margin: 18mm; }
    body { font-family: Arial, Helvetica, sans-serif; font-size: 11pt; line-height: 1.5; color: #1a1a1a; }
    .header h1 { font-size: 20pt; margin: 0 0 4px 0; }
    .subject { font-size: 10pt; color: #666; margin-bottom: 12px; }
    hr { border: none; border-top: 1px solid #ccc; margin: 12px 0; }
    h2 { font-size: 14pt; margin: 18px 0 8px 0; color: #0d9488; }
    h3 { font-size: 12pt; margin: 12px 0 6px 0; color: #0e7490; }
    p { margin: 4px 0; }
    ul { margin: 6px 0 12px 20px; padding: 0; }
    li { margin: 4px 0; }
    .section { margin-bottom: 12px; }
  </style>
</head>
<body>
  ${sections.join('\n')}
  <script>
    window.onload = function() {
      setTimeout(function() { window.print(); }, 300);
    };
  </script>
</body>
</html>`

  const win = window.open('', '_blank')
  if (!win) {
    alert('Please allow pop-ups to download the PDF. In the print dialog, choose "Save as PDF".')
    return
  }
  win.document.open()
  win.document.write(html)
  win.document.close()
}
