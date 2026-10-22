import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Mail, KeyRound, ShieldCheck, Info, AlertTriangle } from 'lucide-react'
import { Logo } from '@/components/common/Logo'
import { Input } from '@/components/common/Input'
import { Button } from '@/components/common/Button'
import { AmbientBackground } from '@/components/common/AmbientBackground'
import { useAuth } from '@/hooks/useAuth'
import * as classService from '@/services/classService'
import type { AuthPolicy } from '@/services/classService'

interface VerifyRouteState {
  email?: string
  /** Only ever present while the backend uses the development console email backend. */
  devVerificationCode?: string | null
}

export default function VerifyEmail() {
  const { verifyEmail, isLoading, error, errorCode, clearError } = useAuth()
  const navigate = useNavigate()
  const location = useLocation() as { state?: VerifyRouteState }

  const [email, setEmail] = useState(location.state?.email ?? '')
  const [code, setCode] = useState('')
  const [policy, setPolicy] = useState<AuthPolicy | null>(null)
  const [devCode, setDevCode] = useState<string | null>(location.state?.devVerificationCode ?? null)
  const [resendMessage, setResendMessage] = useState('')
  const [resendError, setResendError] = useState('')
  const [isResending, setIsResending] = useState(false)
  const [cooldown, setCooldown] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    classService
      .getAuthPolicy()
      .then(setPolicy)
      .catch(() => {
        /* the code length falls back to 6 below */
      })
  }, [])

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [])

  const codeLength = policy?.verificationCodeLength ?? 6

  const startCooldown = (seconds: number) => {
    if (timerRef.current) clearInterval(timerRef.current)
    setCooldown(seconds)
    timerRef.current = setInterval(() => {
      setCooldown((s) => {
        if (s <= 1 && timerRef.current) clearInterval(timerRef.current)
        return Math.max(0, s - 1)
      })
    }, 1000)
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    try {
      await verifyEmail(email, code.trim())
      navigate('/dashboard', { replace: true })
    } catch {
      // error surfaced via auth context
    }
  }

  const handleResend = async () => {
    setIsResending(true)
    setResendError('')
    setResendMessage('')
    clearError()
    try {
      const result = await classService.resendVerificationCode(email)
      setResendMessage(result.message)
      if (result.devVerificationCode) setDevCode(result.devVerificationCode)
      startCooldown(policy?.resendCooldownSeconds ?? 60)
    } catch (err) {
      setResendError(
        err instanceof classService.ApiError
          ? err.message
          : 'Could not request a new code. Is the backend running?'
      )
    } finally {
      setIsResending(false)
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
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/15 text-primary">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <h1 className="text-xl font-semibold text-white">Verify your institute email</h1>
          <p className="mt-1.5 text-sm text-muted">
            We sent a {codeLength}-digit code to your institute address. Your account stays
            inactive until it is confirmed.
          </p>

          {devCode && (
            <div className="mt-5 flex items-start gap-2 rounded-xl border border-cyan/25 bg-cyan/10 px-3.5 py-2.5 text-xs text-cyan">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <p>
                Development mode — no real email was sent. Your code is{' '}
                <span className="font-mono font-semibold tracking-widest">{devCode}</span>
              </p>
            </div>
          )}

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
            <Input
              label="Verification code"
              type="text"
              inputMode="numeric"
              placeholder={'0'.repeat(codeLength)}
              icon={<KeyRound className="h-4 w-4" />}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 12))}
              className="font-mono tracking-[0.3em]"
              autoComplete="one-time-code"
              required
            />

            {error && (
              <p className="rounded-lg bg-red-500/10 px-3.5 py-2.5 text-sm text-red-300">
                {error}
                {errorCode === 'code_expired' && ' Use “Resend code” to get a fresh one.'}
              </p>
            )}

            <Button type="submit" variant="primary" size="lg" fullWidth isLoading={isLoading}>
              Verify &amp; Continue
            </Button>
          </form>

          <div className="mt-5 border-t border-card-border pt-5">
            {resendMessage && (
              <p className="mb-3 rounded-lg bg-emerald-500/10 px-3.5 py-2.5 text-xs text-emerald-300">
                {resendMessage}
              </p>
            )}
            {resendError && (
              <p className="mb-3 flex items-start gap-2 rounded-lg bg-red-500/10 px-3.5 py-2.5 text-xs text-red-300">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                {resendError}
              </p>
            )}

            <Button
              type="button"
              variant="ghost"
              size="sm"
              fullWidth
              onClick={handleResend}
              isLoading={isResending}
              disabled={cooldown > 0 || !email}
            >
              {cooldown > 0 ? `Resend code in ${cooldown}s` : 'Resend code'}
            </Button>
          </div>

          <p className="mt-6 text-center text-sm text-muted">
            Already verified?{' '}
            <Link to="/sign-in" className="text-primary hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
