import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Lock, Eye, EyeOff, CheckCircle2, AlertTriangle } from 'lucide-react'
import { Logo } from '@/components/common/Logo'
import { Input } from '@/components/common/Input'
import { Button } from '@/components/common/Button'
import { AmbientBackground } from '@/components/common/AmbientBackground'
import * as classService from '@/services/classService'

export default function ResetPassword() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const token = params.get('token') ?? ''

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    if (password.length < 6) {
      setError('Password must be at least 6 characters.')
      return
    }
    if (password !== confirm) {
      setError('The two passwords do not match.')
      return
    }
    setIsLoading(true)
    try {
      await classService.resetPassword(token, password)
      setDone(true)
    } catch (err) {
      setError(
        err instanceof classService.ApiError
          ? err.message
          : 'Could not reset your password. Is the backend running?'
      )
    } finally {
      setIsLoading(false)
    }
  }

  const passwordToggle = (
    <button
      type="button"
      onClick={() => setShowPassword((v) => !v)}
      className="text-muted hover:text-white"
      aria-label={showPassword ? 'Hide password' : 'Show password'}
    >
      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
    </button>
  )

  return (
    <div className="relative flex min-h-screen items-center justify-center px-5 py-12">
      <AmbientBackground />
      <div className="w-full max-w-md animate-fade-slide-up">
        <div className="mb-8 flex justify-center">
          <Logo />
        </div>

        <div className="glass-strong rounded-2xl p-7 shadow-glow-lg sm:p-8">
          {!token ? (
            <div className="text-center">
              <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-red-500/15 text-red-300">
                <AlertTriangle className="h-7 w-7" />
              </div>
              <h1 className="text-xl font-semibold text-white">This reset link is incomplete</h1>
              <p className="mt-1.5 text-sm text-muted">
                The link is missing its token. Request a new one and open the link from the email.
              </p>
              <Link to="/forgot-password" className="mt-6 block">
                <Button variant="primary" size="lg" fullWidth>
                  Request a new link
                </Button>
              </Link>
            </div>
          ) : done ? (
            <div className="animate-fade-slide-up text-center">
              <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-500/15 text-emerald-300">
                <CheckCircle2 className="h-7 w-7" />
              </div>
              <h1 className="text-xl font-semibold text-white">Password updated</h1>
              <p className="mt-1.5 text-sm text-muted">
                You can now sign in with your new password. Existing sessions were signed out.
              </p>
              <Button
                variant="primary"
                size="lg"
                fullWidth
                className="mt-6"
                onClick={() => navigate('/sign-in', { replace: true })}
              >
                Go to sign in
              </Button>
            </div>
          ) : (
            <>
              <h1 className="text-xl font-semibold text-white">Choose a new password</h1>
              <p className="mt-1.5 text-sm text-muted">
                This reset link can only be used once.
              </p>

              <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
                <Input
                  label="New password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="At least 6 characters"
                  icon={<Lock className="h-4 w-4" />}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  rightElement={passwordToggle}
                  autoComplete="new-password"
                  required
                />
                <Input
                  label="Confirm new password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Repeat the password"
                  icon={<Lock className="h-4 w-4" />}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  autoComplete="new-password"
                  required
                />

                {error && (
                  <p className="rounded-lg bg-red-500/10 px-3.5 py-2.5 text-sm text-red-300">
                    {error}
                  </p>
                )}

                <Button type="submit" variant="primary" size="lg" fullWidth isLoading={isLoading}>
                  Reset Password
                </Button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
