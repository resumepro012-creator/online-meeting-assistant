const bars = [0, 1, 2, 3, 4, 5, 6, 7]

export function AIActivityVisual({ active = true, size = 'md' }: { active?: boolean; size?: 'sm' | 'md' | 'lg' }) {
  const dims = size === 'lg' ? 'h-44 w-44' : size === 'sm' ? 'h-20 w-20' : 'h-32 w-32'

  return (
    <div className={`relative flex ${dims} shrink-0 items-center justify-center`}>
      {/* Outer glow rings */}
      <span className="absolute inset-0 rounded-full border border-primary/20 animate-ring-spin-slow" />
      <span className="absolute inset-3 rounded-full border border-cyan/25 animate-[ring-spin_4s_linear_infinite_reverse]" />
      <span
        className={`absolute inset-6 rounded-full btn-gradient opacity-20 blur-xl ${active ? 'animate-pulse-glow' : ''}`}
      />

      {/* Core */}
      <div className="glass-strong relative flex h-[58%] w-[58%] items-center justify-center rounded-full shadow-glow">
        <div className="flex items-end gap-1">
          {bars.map((b) => (
            <span
              key={b}
              className={`w-1 rounded-full bg-gradient-to-t from-primary to-cyan ${active ? 'animate-wave' : ''}`}
              style={{
                height: size === 'lg' ? '28px' : size === 'sm' ? '12px' : '20px',
                animationDelay: `${b * 0.09}s`,
                opacity: active ? 1 : 0.35,
              }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
