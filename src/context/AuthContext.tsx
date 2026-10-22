import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import type { Student } from '@/types'
import * as classService from '@/services/classService'
import type { ApiErrorCode, RegisterResult } from '@/services/classService'

interface AuthContextValue {
  student: Student | null
  isAuthenticated: boolean
  /** True while the stored token is being validated against the backend. */
  isRestoring: boolean
  isLoading: boolean
  error: string | null
  /** Machine-readable companion to `error`, so a page can place it on one field. */
  errorCode: ApiErrorCode | null
  login: (email: string, password: string) => Promise<void>
  /**
   * Creates an inactive account and sends a verification code. It does **not**
   * sign the student in — the account stays unusable until `verifyEmail`.
   */
  signUp: (name: string, email: string, password: string) => Promise<RegisterResult>
  /** Confirms the emailed code and signs the student in. */
  verifyEmail: (email: string, code: string) => Promise<void>
  clearError: () => void
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

const STORAGE_KEY = 'ai-class-assistant.student'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [student, setStudent] = useState<Student | null>(() => {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY)
      return raw ? (JSON.parse(raw) as Student) : null
    } catch {
      return null
    }
  })
  const [isRestoring, setIsRestoring] = useState(true)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [errorCode, setErrorCode] = useState<ApiErrorCode | null>(null)

  const persist = (s: Student | null) => {
    setStudent(s)
    try {
      if (s) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(s))
      else sessionStorage.removeItem(STORAGE_KEY)
    } catch {
      // sessionStorage unavailable — the session simply won't persist across reloads
    }
  }

  const clearError = () => {
    setError(null)
    setErrorCode(null)
  }

  const fail = (e: unknown, fallback: string) => {
    if (e instanceof classService.ApiError) {
      setError(e.message)
      setErrorCode(e.code)
    } else {
      setError(e instanceof Error ? e.message : fallback)
      setErrorCode(null)
    }
  }

  /**
   * A reload keeps the cached student, but the access token may have expired,
   * so confirm it against `GET /api/auth/me` before trusting the cached copy.
   */
  useEffect(() => {
    let cancelled = false
    if (!classService.hasAccessToken()) {
      persist(null)
      setIsRestoring(false)
      return
    }
    classService
      .getCurrentStudent()
      .then((fresh) => {
        if (!cancelled) persist(fresh)
      })
      .catch(() => {
        if (!cancelled) {
          classService.logout()
          persist(null)
        }
      })
      .finally(() => {
        if (!cancelled) setIsRestoring(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const login = async (email: string, password: string) => {
    setIsLoading(true)
    clearError()
    try {
      if (!email || !password) {
        throw new Error('Please enter both your email and password.')
      }
      const result = await classService.login(email, password)
      persist(result)
    } catch (e) {
      fail(e, 'Something went wrong signing you in.')
      throw e
    } finally {
      setIsLoading(false)
    }
  }

  const signUp = async (name: string, email: string, password: string) => {
    setIsLoading(true)
    clearError()
    try {
      if (!name || !email || !password) {
        throw new Error('Please fill in your name, email, and password.')
      }
      // Deliberately not persisted: the account is inactive until verified.
      return await classService.signUp(name, email, password)
    } catch (e) {
      fail(e, 'Something went wrong creating your account.')
      throw e
    } finally {
      setIsLoading(false)
    }
  }

  const verifyEmail = async (email: string, code: string) => {
    setIsLoading(true)
    clearError()
    try {
      if (!email || !code) {
        throw new Error('Please enter the verification code we emailed you.')
      }
      const result = await classService.verifyEmail(email, code)
      persist(result)
    } catch (e) {
      fail(e, 'That verification code could not be confirmed.')
      throw e
    } finally {
      setIsLoading(false)
    }
  }

  const logout = () => {
    classService.logout()
    persist(null)
    clearError()
  }

  return (
    <AuthContext.Provider
      value={{
        student,
        isAuthenticated: !!student,
        isRestoring,
        isLoading,
        error,
        errorCode,
        login,
        signUp,
        verifyEmail,
        clearError,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuthContext(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuthContext must be used within AuthProvider')
  return ctx
}
