import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  hover?: boolean
  strong?: boolean
}

export function Card({ className, hover = false, strong = false, children, ...props }: CardProps) {
  return (
    <div
      className={cn(
        strong ? 'glass-strong' : 'glass',
        'rounded-2xl p-5 transition-all duration-300',
        hover && 'hover:-translate-y-1 hover:shadow-glow hover:border-primary/40 cursor-pointer',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}
