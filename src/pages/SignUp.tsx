import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { User, Mail, Lock, Eye, EyeOff, Info } from 'lucide-react'
import { Logo } from '@/components/common/Logo'
import { Input } from '@/components/common/Input'
import { Button } from '@/components/common/Button'
import { AmbientBackground } from '@/components/common/AmbientBackground'
import { useAuth } from '@/hooks/useAuth'
import * as classService from '@/services/classService'
import type { AuthPolicy } from '@/services/classService'

/** Shown under the email field — matches the backend's wording. */
const INSTITUTE_EMAIL_MESSAGE = 'Please register with your institute email address.'

export default function SignUp() {
  const { signUp, isLoading, error, errorCode, clearError } = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [policy, setPolicy] = useState<AuthPolicy | null>(null)
  const [domainError, setDomainError] = useState('')
  const [validationError, setValidationError] = useState('')

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
    if (errorCode === 'email_domain_not_allowed' || errorCode === 'email_already_registered') {
      clearError()
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setValidationError('')
    setDomainError('')

    if (password.length < 6) {
      setValidationError('Password must be at least 6 characters.')
      return
    }
    if (!domainIsAllowed(email)) {
      setDomainError(INSTITUTE_EMAIL_MESSAGE)
      return
    }

    try {
      const result = await signUp(name, email, password)
      // The account exists but stays inactive until the emailed code is entered.
      navigate('/verify-email', {
        state: { email: result.email, devVerificationCode: result.devVerificationCode ?? null },
      })
    } catch {
      // error surfaced via auth context
    }
  }

  const emailError =
    domainError ||
    (errorCode === 'email_domain_not_allowed'
      ? error ?? INSTITUTE_EMAIL_MESSAGE
      : errorCode === 'email_already_registered'
        ? error ?? 'An account with this email already exists.'
        : '')
  const showBanner =
    !!error && errorCode !== 'email_domain_not_allowed' && errorCode !== 'email_already_registered'

  return (
    <div className="relative flex min-h-screen items-center justify-center px-5 py-12">
      <AmbientBackground />
      <div className="w-full max-w-md animate-fade-slide-up">
        <div className="mb-8 flex justify-center">
          <Logo />
        </div>

        <div className="glass-strong rounded-2xl p-7 shadow-glow-lg sm:p-8">
          <h1 className="text-xl font-semibold text-white">Create your account</h1>
          <p className="mt-1.5 text-sm text-muted">Start letting AI take notes for you.</p>

          <div className="mt-5 flex items-start gap-2 rounded-xl border border-cyan/25 bg-cyan/10 px-3.5 py-2.5 text-xs text-cyan">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <p>
              Registration is limited to institute email addresses (e.g.{' '}
              <span className="font-medium">you@{exampleDomain}</span> or any{' '}
              <span className="font-medium">.edu</span> address). We&apos;ll email you a code to
              verify the address.
            </p>
          </div>

          <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
            <Input
              label="Full name"
              type="text"
              placeholder="Ayesha Khan"
              icon={<User className="h-4 w-4" />}
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoComplete="name"
              required
            />
            <Input
              label="Institute email"
              type="email"
              placeholder={`you@${exampleDomain}`}
              icon={<Mail className="h-4 w-4" />}
              value={email}
              onChange={(e) => handleEmailChange(e.target.value)}
              error={emailError || undefined}
              autoComplete="email"
              required
            />
            <Input
              label="Password"
              type={showPassword ? 'text' : 'password'}
              placeholder="At least 6 characters"
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
              autoComplete="new-password"
              required
            />

            {(showBanner || validationError) && (
              <p className="rounded-lg bg-red-500/10 px-3.5 py-2.5 text-sm text-red-300">
                {validationError || error}
              </p>
            )}

            <Button type="submit" variant="primary" size="lg" fullWidth isLoading={isLoading}>
              Create Account
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-muted">
            Already have an account?{' '}
            <Link to="/sign-in" className="text-primary hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
