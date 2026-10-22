import { useMemo } from 'react'

/**
 * Fixed, decorative grid + particle backdrop used across pages for the
 * futuristic AI look. Purely visual — sits behind content, ignores pointer
 * events, and respects prefers-reduced-motion via the pulse-glow animation
 * being disabled globally in index.css.
 */
export function AmbientBackground() {
  const particles = useMemo(
    () =>
      Array.from({ length: 18 }, (_, i) => ({
        id: i,
        top: Math.random() * 100,
        left: Math.random() * 100,
        delay: Math.random() * 3,
        size: 2 + Math.random() * 3,
      })),
    []
  )

  return (
    <div className="fixed inset-0 -z-10 overflow-hidden">
      <div className="grid-field" />
      <div className="particle-field">
        {particles.map((p) => (
          <span
            key={p.id}
            className="particle animate-pulse-glow"
            style={{
              top: `${p.top}%`,
              left: `${p.left}%`,
              width: p.size,
              height: p.size,
              animationDelay: `${p.delay}s`,
            }}
          />
        ))}
      </div>
    </div>
  )
}
