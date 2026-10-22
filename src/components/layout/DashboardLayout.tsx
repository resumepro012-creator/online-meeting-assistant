import { useState, type ReactNode } from 'react'
import { X } from 'lucide-react'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import { AmbientBackground } from '@/components/common/AmbientBackground'

export function DashboardLayout({ title, children }: { title: string; children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="relative min-h-screen">
      <AmbientBackground />

      <div className="flex min-h-screen">
        {/* Desktop sidebar */}
        <div className="hidden lg:block">
          <Sidebar />
        </div>

        {/* Mobile drawer */}
        {mobileOpen && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <div
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
              onClick={() => setMobileOpen(false)}
              aria-hidden="true"
            />
            <div className="absolute inset-y-0 left-0 animate-fade-slide-up">
              <div className="relative h-full">
                <button
                  onClick={() => setMobileOpen(false)}
                  aria-label="Close navigation"
                  className="absolute right-[-44px] top-6 rounded-lg border border-card-border bg-card p-2 text-white"
                >
                  <X className="h-4 w-4" />
                </button>
                <Sidebar onNavigate={() => setMobileOpen(false)} />
              </div>
            </div>
          </div>
        )}

        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar title={title} onMenuClick={() => setMobileOpen(true)} />
          <main className="flex-1 px-5 py-6 lg:px-8 lg:py-8">
            <div className="mx-auto w-full max-w-7xl">{children}</div>
          </main>
        </div>
      </div>
    </div>
  )
}
