import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Mail, Info, CheckCircle2, ArrowLeft } from 'lucide-react'
import { Logo } from '@/components/common/Logo'
import { Input } from '@/components/common/Input'
import { Button } from '@/components/common/Button'
import { AmbientBackground } from '@/components/common/AmbientBackground'
import * as classService from '@/services/classService'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError('')
    try {
      setMessage(await classService.forgotPassword(email))
      setSent(true)
    } catch (err) {
      setError(
        err instanceof classService.ApiError
          ? err.message
          : 'Could not send the reset email. Is the backend running?'
      )
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center px-5 py-12">
      <AmbientBackground />
      <div className="w-full max-w-md animate-fade-slide-up">
        <div className="mb-8 flex justify-center">
          <Logo />
        </div>

        <div className="glass-strong rounded-2xl p-7 shadow-glow-lg sm:p-8">
          {!sent ? (
            <>
              <h1 className="text-xl font-semibold text-white">Reset your password</h1>
              <p className="mt-1.5 text-sm text-muted">
                Enter your institute email and we&apos;ll send you a reset link.
              </p>

              <div className="mt-5 flex items-start gap-2 rounded-xl border border-cyan/25 bg-cyan/10 px-3.5 py-2.5 text-xs text-cyan">
                <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <p>
                  For your security we don&apos;t reveal whether an address is registered — the
                  response is the same either way.
                </p>
              </div>

              <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
                <Input
                  label="Institute email"
                  type="email"
                  placeholder="you@your-institute.edu"
                  icon={<Mail className="h-4 w-4" />}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  required
                />

                {error && (
                  <p className="rounded-lg bg-red-500/10 px-3.5 py-2.5 text-sm text-red-300">
                    {error}
                  </p>
                )}

                <Button type="submit" variant="primary" size="lg" fullWidth isLoading={isLoading}>
                  Send Reset Link
                </Button>
              </form>
            </>
          ) : (
            <div className="animate-fade-slide-up text-center">
              <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-500/15 text-emerald-300">
                <CheckCircle2 className="h-7 w-7" />
              </div>
              <h1 className="text-xl font-semibold text-white">Check your email</h1>
              <p className="mt-1.5 text-sm text-muted">{message}</p>
              <p className="mt-2 text-xs text-muted">
                The link expires shortly, so open it soon.
              </p>
              <Link
                to="/sign-in"
                className="mt-6 inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
              >
                <ArrowLeft className="h-4 w-4" />
                Back to sign in
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
