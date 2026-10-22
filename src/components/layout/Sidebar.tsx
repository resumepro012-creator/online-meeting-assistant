import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  Video,
  History,
  NotebookText,
  Megaphone,
  Settings,
  LogOut,
} from 'lucide-react'
import { Logo } from '@/components/common/Logo'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'

const navItems = [
  { label: 'Dashboard', to: '/dashboard', icon: LayoutDashboard },
  { label: 'Join Class', to: '/join-class', icon: Video },
  { label: 'My Classes', to: '/my-classes', icon: History },
  { label: 'Lecture Notes', to: '/lecture-notes', icon: NotebookText },
  { label: 'Announcements', to: '/announcements', icon: Megaphone },
  { label: 'Settings', to: '/settings', icon: Settings },
]

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <aside className="flex h-full w-64 flex-col border-r border-white/5 bg-bg-deep/60 px-4 py-6">
      <div className="mb-8 px-2">
        <Logo />
      </div>

      <nav className="flex-1 space-y-1">
        {navItems.map(({ label, to, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                'group flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-all duration-200',
                isActive
                  ? 'bg-primary/12 text-white shadow-[inset_0_0_0_1px_rgba(77,163,255,0.35)]'
                  : 'text-muted hover:bg-white/5 hover:text-white'
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon className={cn('h-4.5 w-4.5', isActive && 'text-primary drop-shadow-[0_0_6px_rgba(77,163,255,0.7)]')} />
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <button
        onClick={handleLogout}
        className="flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium text-muted transition-colors hover:bg-red-500/10 hover:text-red-300"
      >
        <LogOut className="h-4.5 w-4.5" />
        Logout
      </button>
    </aside>
  )
}
