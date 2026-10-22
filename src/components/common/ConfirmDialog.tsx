import { AlertTriangle, X } from 'lucide-react'
import { Button } from './Button'

interface ConfirmDialogProps {
  open: boolean
  title: string
  description: string
  confirmLabel?: string
  cancelLabel?: string
  destructive?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  destructive = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4 animate-fade-slide-up"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
    >
      <div className="glass-strong relative w-full max-w-sm rounded-2xl p-6 shadow-glow-lg">
        <button
          onClick={onCancel}
          aria-label="Close dialog"
          className="absolute right-4 top-4 text-muted hover:text-white"
        >
          <X className="h-4 w-4" />
        </button>
        <div
          className={`mb-4 flex h-11 w-11 items-center justify-center rounded-xl ${
            destructive ? 'bg-red-500/15 text-red-300' : 'bg-primary/15 text-primary'
          }`}
        >
          <AlertTriangle className="h-5 w-5" />
        </div>
        <h3 id="confirm-dialog-title" className="text-base font-semibold text-white">
          {title}
        </h3>
        <p className="mt-1.5 text-sm text-muted">{description}</p>
        <div className="mt-6 flex gap-3">
          <Button variant="secondary" size="md" fullWidth onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button variant={destructive ? 'danger' : 'primary'} size="md" fullWidth onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}
