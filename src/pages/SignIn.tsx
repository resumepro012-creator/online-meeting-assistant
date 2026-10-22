import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Mail, Lock, Eye, EyeOff, ShieldCheck, Info } from 'lucide-react'
import { Logo } from '@/components/common/Logo'
import { Input } from '@/components/common/Input'
import { Button } from '@/components/common/Button'
import { AmbientBackground } from '@/components/common/AmbientBackground'
import { useAuth } from '@/hooks/useAuth'
import * as classService from '@/services/classService'
import type { AuthPolicy } from '@/services/classService'

/** Shown under the email field — also the message the backend returns. */
const INSTITUTE_EMAIL_MESSAGE = 'Please login with institute mail.'

export default function SignIn() {
  const { login, isLoading, error, errorCode, clearError } = useAuth()
  const navigate = useNavigate()
  const location = useLocation() as { state?: { from?: string } }
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [policy, setPolicy] = useState<AuthPolicy | null>(null)
  const [domainError, setDomainError] = useState('')

  // The approved domains are read from the backend — never hardcoded here.
  useEffect(() => {
    classService
      .getAuthPolicy()
      .then(setPolicy)
      .catch(() => {
        /* the backend still validates the domain on submit */
      })
  }, [])

  const exampleDomain =
    policy?.universityEmailDomains[0] ?? policy?.allowedEmailDomains[0] ?? 'your-institute.edu'

  const domainIsAllowed = (value: string): boolean => {
    if (!policy || !value.includes('@')) return true
    return classService.isAllowedUniversityEmail(value, policy)
  }

  const handleEmailChange = (value: string) => {
    setEmail(value)
    setDomainError('')
    if (errorCode === 'email_domain_not_allowed') clearError()
  }

  const handleEmailBlur = () => {
    if (email && !domainIsAllowed(email)) setDomainError(INSTITUTE_EMAIL_MESSAGE)
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!domainIsAllowed(email)) {
      setDomainError(INSTITUTE_EMAIL_MESSAGE)
      return
    }
    try {
      await login(email, password)
      navigate(location.state?.from ?? '/dashboard')
    } catch {
      // error surfaced via auth context
    }
  }

  const emailError =
    domainError ||
    (errorCode === 'email_domain_not_allowed' ? error ?? INSTITUTE_EMAIL_MESSAGE : '')
  const showBanner = !!error && errorCode !== 'email_domain_not_allowed'

  return (
    <div className="relative flex min-h-screen items-center justify-center px-5 py-12">
      <AmbientBackground />
      <div className="w-full max-w-md animate-fade-slide-up">
        <div className="mb-8 flex justify-center">
          <Logo />
        </div>

        <div className="glass-strong rounded-2xl p-7 shadow-glow-lg sm:p-8">
          <h1 className="text-xl font-semibold text-white">Welcome back</h1>
          <p className="mt-1.5 text-sm text-muted">Sign in to continue to your dashboard.</p>

          <div className="mt-5 flex items-start gap-2 rounded-xl border border-cyan/25 bg-cyan/10 px-3.5 py-2.5 text-xs text-cyan">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <p>
              Institute accounts only. Sign in with your institute address (e.g.{' '}
              <span className="font-medium">you@{exampleDomain}</span> or any{' '}
              <span className="font-medium">.edu</span> address).
            </p>
          </div>

          <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
            <Input
              label="Email"
              type="email"
              placeholder={`you@${exampleDomain}`}
              icon={<Mail className="h-4 w-4" />}
              value={email}
              onChange={(e) => handleEmailChange(e.target.value)}
              onBlur={handleEmailBlur}
              error={emailError || undefined}
              autoComplete="email"
              required
            />
            <Input
              label="Password"
              type={showPassword ? 'text' : 'password'}
              placeholder="••••••••"
              icon={<Lock className="h-4 w-4" />}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              rightElement={
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="text-muted hover:text-white"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              }
              autoComplete="current-password"
              required
              minLength={6}
            />

            <div className="flex justify-end">
              <Link to="/forgot-password" className="text-xs text-primary hover:underline">
                Forgot password?
              </Link>
            </div>

            {showBanner && (
              <div className="rounded-lg bg-red-500/10 px-3.5 py-2.5 text-sm text-red-300">
                <p>{error}</p>
                {errorCode === 'email_not_verified' && (
                  <Link
                    to="/verify-email"
                    state={{ email }}
                    className="mt-1.5 inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
                  >
                    <ShieldCheck className="h-3.5 w-3.5" />
                    Enter your verification code
                  </Link>
                )}
              </div>
            )}

            <Button type="submit" variant="primary" size="lg" fullWidth isLoading={isLoading}>
              Sign In
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-muted">
            Don&apos;t have an account?{' '}
            <Link to="/sign-up" className="text-primary hover:underline">
              Create one
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
