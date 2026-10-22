import { Link } from 'react-router-dom'
import {
  Video,
  BrainCircuit,
  NotebookPen,
  Megaphone,
  ArrowRight,
  FileText,
  Waves,
  ListChecks,
  LayoutDashboard,
} from 'lucide-react'
import { Navbar } from '@/components/layout/Navbar'
import { Button } from '@/components/common/Button'
import { Card } from '@/components/common/Card'
import { AmbientBackground } from '@/components/common/AmbientBackground'
import { Badge } from '@/components/common/Badge'

const features = [
  {
    icon: Video,
    title: 'Join Online Classes',
    description: 'Drop in your meeting link or upload a recording — your class session starts in one click.',
  },
  {
    icon: BrainCircuit,
    title: 'AI Lecture Analysis',
    description: 'The assistant listens for structure, emphasis, and key terms as the lecture unfolds.',
  },
  {
    icon: NotebookPen,
    title: 'Automatic Lecture Notes',
    description: 'Walk away with organized, section-by-section notes instead of a messy transcript.',
  },
  {
    icon: Megaphone,
    title: 'Important Announcements',
    description: 'Assignments, quizzes, and deadlines your teacher mentions are pulled out automatically.',
  },
]

const steps = [
  { icon: Video, title: 'Join Class', description: 'Connect your meeting link or upload lecture audio.' },
  { icon: Waves, title: 'AI Processes Lecture', description: 'Speech is transcribed and analyzed for structure and meaning.' },
  { icon: ListChecks, title: 'Notes & Announcements', description: 'Organized notes and teacher announcements are generated.' },
  { icon: LayoutDashboard, title: 'Student Dashboard', description: 'Everything lands in one place, ready to review.' },
]

const floatingChips = [
  { label: 'Transcription', icon: FileText, style: 'left-2 top-6' },
  { label: 'Lecture Notes', icon: NotebookPen, style: 'right-0 top-2' },
  { label: 'Key Concepts', icon: BrainCircuit, style: 'left-0 bottom-16' },
  { label: 'Announcements', icon: Megaphone, style: 'right-2 bottom-4' },
]

export default function Landing() {
  return (
    <div className="relative min-h-screen overflow-x-hidden">
      <AmbientBackground />
      <Navbar />

      {/* Hero */}
      <section className="relative mx-auto max-w-7xl px-5 pb-20 pt-16 lg:px-8 lg:pb-28 lg:pt-24">
        <div className="grid items-center gap-14 lg:grid-cols-2 lg:gap-10">
          <div className="animate-fade-slide-up">
            <Badge tone="cyan" className="mb-5">
              Deep Learning powered
            </Badge>
            <h1 className="text-4xl font-semibold leading-[1.1] tracking-tight text-white sm:text-5xl lg:text-[3.4rem]">
              Your AI Assistant for Online Classes
            </h1>
            <p className="mt-5 max-w-lg text-base leading-relaxed text-muted sm:text-lg">
              Join your online classes while AI helps generate organized lecture notes and capture important
              teacher announcements automatically.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link to="/sign-in">
                <Button variant="primary" size="lg" fullWidth className="sm:w-auto">
                  Join Your Class
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <a href="#features">
                <Button variant="secondary" size="lg" fullWidth className="sm:w-auto">
                  Explore Features
                </Button>
              </a>
            </div>
          </div>

          {/* Illustration */}
          <div className="relative mx-auto w-full max-w-md animate-fade-slide-up [animation-delay:150ms]">
            <div className="glass-strong relative rounded-3xl p-6 shadow-glow-lg">
              <div className="grid-field rounded-2xl opacity-60" />
              <div className="relative flex flex-col items-center gap-6 py-8">
                <div className="relative flex h-40 w-40 items-center justify-center">
                  <span className="absolute inset-0 rounded-full border border-primary/25 animate-ring-spin-slow" />
                  <span className="absolute inset-4 rounded-full border border-cyan/30 animate-[ring-spin_5s_linear_infinite_reverse]" />
                  <span className="absolute inset-8 rounded-full btn-gradient opacity-30 blur-2xl animate-pulse-glow" />
                  <div className="glass relative flex h-20 w-20 items-center justify-center rounded-full shadow-glow">
                    <BrainCircuit className="h-8 w-8 text-cyan" />
                  </div>
                </div>
                <div className="text-center">
                  <p className="text-sm font-medium text-white">Lecture in progress</p>
                  <p className="font-mono text-xs text-muted">analyzing audio stream…</p>
                </div>
              </div>

              {floatingChips.map((chip) => (
                <span
                  key={chip.label}
                  className={`glass absolute hidden items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium text-white shadow-glow-sm sm:flex ${chip.style}`}
                >
                  <chip.icon className="h-3.5 w-3.5 text-cyan" />
                  {chip.label}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Feature cards */}
        <div id="features" className="mt-20 grid grid-cols-1 gap-5 scroll-mt-24 sm:grid-cols-2 lg:grid-cols-4">
          {features.map((f, i) => (
            <Card
              key={f.title}
              hover
              className="animate-fade-slide-up"
              style={{ animationDelay: `${i * 80}ms` }}
            >
              <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl border border-primary/30 bg-primary/10 text-primary">
                <f.icon className="h-5 w-5" />
              </div>
              <p className="text-base font-semibold text-white">{f.title}</p>
              <p className="mt-1.5 text-sm leading-relaxed text-muted">{f.description}</p>
            </Card>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="relative scroll-mt-24 border-t border-white/5 bg-bg-deep/40 py-20">
        <div className="mx-auto max-w-7xl px-5 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-semibold tracking-tight text-white">How It Works</h2>
            <p className="mt-3 text-muted">From joining a class to reviewing what mattered, in four steps.</p>
          </div>

          <div className="relative mt-14 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
            <div className="absolute left-0 right-0 top-6 hidden h-px bg-gradient-to-r from-transparent via-primary/30 to-transparent lg:block" />
            {steps.map((s, i) => (
              <div key={s.title} className="relative flex flex-col items-center text-center">
                <div className="glass relative z-10 flex h-12 w-12 items-center justify-center rounded-xl text-primary shadow-glow-sm">
                  <s.icon className="h-5 w-5" />
                </div>
                <p className="mt-4 text-sm font-semibold text-white">
                  {i + 1}. {s.title}
                </p>
                <p className="mt-1.5 max-w-[220px] text-sm text-muted">{s.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="relative border-t border-white/5 py-20">
        <div className="mx-auto max-w-4xl px-5 text-center lg:px-8">
          <div className="glass-strong rounded-3xl px-8 py-14 shadow-glow">
            <h2 className="text-3xl font-semibold tracking-tight text-white">Ready for your next class?</h2>
            <p className="mx-auto mt-3 max-w-md text-muted">
              Create a free account and let your next lecture take care of its own notes.
            </p>
            <div className="mt-7 flex flex-col justify-center gap-3 sm:flex-row">
              <Link to="/sign-up">
                <Button variant="primary" size="lg" fullWidth className="sm:w-auto">
                  Create Account
                </Button>
              </Link>
              <Link to="/sign-in">
                <Button variant="secondary" size="lg" fullWidth className="sm:w-auto">
                  Sign In
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 py-10">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-5 sm:flex-row lg:px-8">
          <p className="text-sm text-muted">© {new Date().getFullYear()} AI Class Assistant. A Deep Learning project.</p>
          <p className="text-xs text-muted">Built with React, Vite &amp; Tailwind CSS</p>
        </div>
      </footer>
    </div>
  )
}
