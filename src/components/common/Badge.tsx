import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

type Tone = 'blue' | 'cyan' | 'green' | 'amber' | 'red' | 'violet' | 'neutral'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone
}

const toneStyles: Record<Tone, string> = {
  blue: 'bg-primary/15 text-primary border-primary/30',
  cyan: 'bg-cyan/15 text-cyan border-cyan/30',
  green: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  amber: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  red: 'bg-red-500/15 text-red-300 border-red-500/30',
  violet: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
  neutral: 'bg-white/8 text-muted border-white/15',
}

export function Badge({ className, tone = 'neutral', children, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium',
        toneStyles[tone],
        className
      )}
      {...props}
    >
      {children}
    </span>
  )
}
