import { Link } from 'react-router-dom'
import { Compass } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { AmbientBackground } from '@/components/common/AmbientBackground'
import { Logo } from '@/components/common/Logo'

export default function NotFound() {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center px-5 text-center">
      <AmbientBackground />
      <div className="mb-8">
        <Logo />
      </div>
      <div className="glass flex h-16 w-16 items-center justify-center rounded-2xl text-primary shadow-glow-sm">
        <Compass className="h-7 w-7" />
      </div>
      <h1 className="mt-6 text-3xl font-semibold text-white">Page not found</h1>
      <p className="mt-2 max-w-sm text-sm text-muted">
        The page you&apos;re looking for doesn&apos;t exist or has moved.
      </p>
      <Link to="/" className="mt-7">
        <Button variant="primary" size="md">
          Back to Home
        </Button>
      </Link>
    </div>
  )
}
