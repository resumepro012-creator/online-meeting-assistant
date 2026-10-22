import { useState } from 'react'
import { Bell, Menu, Search, ChevronDown } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'

export function Topbar({ title, onMenuClick }: { title: string; onMenuClick: () => void }) {
  const { student, logout } = useAuth()
  const [profileOpen, setProfileOpen] = useState(false)

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-4 border-b border-white/5 bg-bg/80 px-5 py-4 backdrop-blur-xl lg:px-8">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          className="rounded-lg p-2 text-white lg:hidden"
          aria-label="Open navigation"
        >
          <Menu className="h-5 w-5" />
        </button>
        <h1 className="text-lg font-semibold text-white">{title}</h1>
      </div>

      <div className="hidden max-w-xs flex-1 items-center gap-2 rounded-xl border border-card-border bg-card/60 px-3.5 py-2 md:flex">
        <Search className="h-4 w-4 text-muted" />
        <input
          type="text"
          placeholder="Search classes, notes..."
          className="w-full bg-transparent text-sm text-white placeholder:text-muted/70 focus:outline-none"
        />
      </div>

      <div className="flex items-center gap-3">
        <button
          className="relative rounded-xl border border-card-border bg-card/60 p-2.5 text-muted hover:text-white"
          aria-label="Notifications"
        >
          <Bell className="h-4.5 w-4.5" />
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-cyan shadow-[0_0_6px_rgba(99,217,255,0.9)]" />
        </button>

        <div className="relative">
          <button
            onClick={() => setProfileOpen((v) => !v)}
            className="flex items-center gap-2 rounded-xl border border-card-border bg-card/60 px-2.5 py-1.5 hover:border-primary/40"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-lg btn-gradient text-xs font-semibold text-[#06101F]">
              {student?.avatarInitials ?? 'ST'}
            </span>
            <span className="hidden text-sm text-white sm:inline">{student?.name ?? 'Student'}</span>
            <ChevronDown className="hidden h-3.5 w-3.5 text-muted sm:inline" />
          </button>

          {profileOpen && (
            <div className="absolute right-0 top-full mt-2 w-44 rounded-xl border border-card-border bg-card-light py-1.5 shadow-glow-lg">
              <p className="truncate px-3.5 py-2 text-xs text-muted">{student?.email}</p>
              <button
                onClick={() => {
                  setProfileOpen(false)
                  logout()
                  window.location.href = '/'
                }}
                className="w-full px-3.5 py-2 text-left text-sm text-red-300 hover:bg-white/5"
              >
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
