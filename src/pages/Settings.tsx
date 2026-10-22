import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { User, Mail, Moon, Sun, LogOut, Info, Check } from 'lucide-react'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Card } from '@/components/common/Card'
import { Input } from '@/components/common/Input'
import { Button } from '@/components/common/Button'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'

export default function Settings() {
  const { student, logout } = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState(student?.name ?? '')
  const [email, setEmail] = useState(student?.email ?? '')
  const [theme, setTheme] = useState<'dark' | 'system'>('dark')
  const [saved, setSaved] = useState(false)
  const [confirmLogout, setConfirmLogout] = useState(false)

  const handleSave = () => {
    setSaved(true)
    setTimeout(() => setSaved(false), 1800)
  }

  return (
    <DashboardLayout title="Settings">
      <div className="mx-auto max-w-2xl space-y-6">
        <Card>
          <h3 className="text-base font-semibold text-white">Profile</h3>
          <p className="mt-1 text-sm text-muted">Update your basic student information.</p>

          <div className="mt-5 space-y-4">
            <Input label="Full name" icon={<User className="h-4 w-4" />} value={name} onChange={(e) => setName(e.target.value)} />
            <Input label="Email" icon={<Mail className="h-4 w-4" />} value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>

          <div className="mt-5 flex items-start gap-2 rounded-xl border border-cyan/25 bg-cyan/10 px-3.5 py-2.5 text-xs text-cyan">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <p>Demo Mode — changes are kept for this session only and are not saved to a real account.</p>
          </div>

          <Button variant="primary" size="md" className="mt-5" onClick={handleSave}>
            {saved ? <Check className="h-4 w-4" /> : null}
            {saved ? 'Saved' : 'Save Changes'}
          </Button>
        </Card>

        <Card>
          <h3 className="text-base font-semibold text-white">Theme Preference</h3>
          <p className="mt-1 text-sm text-muted">Choose how AI Class Assistant looks.</p>

          <div className="mt-4 grid grid-cols-2 gap-3">
            <button
              onClick={() => setTheme('dark')}
              className={cn(
                'flex flex-col items-center gap-2 rounded-xl border px-4 py-4 text-sm transition-colors',
                theme === 'dark' ? 'border-primary/50 bg-primary/10 text-white' : 'border-card-border text-muted hover:text-white'
              )}
            >
              <Moon className="h-5 w-5" />
              Dark (default)
            </button>
            <button
              onClick={() => setTheme('system')}
              className={cn(
                'flex flex-col items-center gap-2 rounded-xl border px-4 py-4 text-sm transition-colors',
                theme === 'system' ? 'border-primary/50 bg-primary/10 text-white' : 'border-card-border text-muted hover:text-white'
              )}
            >
              <Sun className="h-5 w-5" />
              Match System
            </button>
          </div>
          <p className="mt-3 text-xs text-muted">
            This project is designed dark-first; light mode is not yet implemented in this demo.
          </p>
        </Card>

        <Card>
          <h3 className="text-base font-semibold text-white">Account</h3>
          <p className="mt-1 text-sm text-muted">Signed in as a demo student session.</p>
          <Button variant="danger" size="md" className="mt-4" onClick={() => setConfirmLogout(true)}>
            <LogOut className="h-4 w-4" />
            Logout
          </Button>
        </Card>
      </div>

      <ConfirmDialog
        open={confirmLogout}
        title="Log out?"
        description="You'll need to sign in again to access your dashboard."
        confirmLabel="Logout"
        destructive
        onConfirm={() => {
          setConfirmLogout(false)
          logout()
          navigate('/')
        }}
        onCancel={() => setConfirmLogout(false)}
      />
    </DashboardLayout>
  )
}
