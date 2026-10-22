import { Link } from 'react-router-dom'
import { Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'

export function Logo({ className }: { className?: string }) {
  return (
    <Link to="/" className={cn('flex items-center gap-2.5', className)}>
      <span className="relative flex h-9 w-9 items-center justify-center rounded-xl btn-gradient shadow-glow-sm">
        <Sparkles className="h-4.5 w-4.5 text-[#06101F]" strokeWidth={2.5} />
      </span>
      <span className="text-lg font-semibold tracking-tight text-white">
        AI Class <span className="text-gradient">Assistant</span>
      </span>
    </Link>
  )
}
