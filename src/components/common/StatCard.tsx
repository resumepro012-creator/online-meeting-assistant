import type { LucideIcon } from 'lucide-react'
import { Card } from './Card'

interface StatCardProps {
  label: string
  value: string | number
  icon: LucideIcon
  tone?: 'blue' | 'cyan'
}

export function StatCard({ label, value, icon: Icon, tone = 'blue' }: StatCardProps) {
  return (
    <Card className="flex items-center gap-4">
      <div
        className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border ${
          tone === 'blue' ? 'bg-primary/10 border-primary/30 text-primary' : 'bg-cyan/10 border-cyan/30 text-cyan'
        }`}
      >
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <p className="text-2xl font-semibold text-white leading-none">{value}</p>
        <p className="mt-1 text-sm text-muted">{label}</p>
      </div>
    </Card>
  )
}
