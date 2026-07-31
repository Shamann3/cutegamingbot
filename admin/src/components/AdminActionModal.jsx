import { useEffect, useId, useRef } from 'react'

export default function AdminActionModal({
  open,
  title,
  description,
  confirmText = 'OK',
  cancelText = 'Отмена',
  danger = false,
  loading = false,
  showReason = false,
  reason = '',
  onReasonChange,
  reasonPlaceholder = 'Сообщение игроку в боте',
  reasonRequired = false,
  onConfirm,
  onCancel,
}) {
  const titleId = useId()
  const dialogRef = useRef(null)
  const confirmRef = useRef(null)
  const reasonOk = !reasonRequired || String(reason || '').trim().length > 0

  useEffect(() => {
    if (!open) return undefined
    const prev = document.activeElement
    const t = window.setTimeout(() => {
      if (showReason) {
        dialogRef.current?.querySelector('textarea')?.focus()
      } else {
        confirmRef.current?.focus()
      }
    }, 0)
    return () => {
      window.clearTimeout(t)
      if (prev && typeof prev.focus === 'function') {
        try { prev.focus() } catch { /* ignore */ }
      }
    }
  }, [open, showReason])

  if (!open) return null

  return (
    <div
      className="admin-modal-backdrop"
      role="presentation"
      onClick={() => {
        if (!loading) onCancel?.()
      }}
    >
      <div
        ref={dialogRef}
        className="admin-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 id={titleId} className="admin-modal-title">
          {title}
        </h3>
        {description && <p className="admin-modal-desc">{description}</p>}
        {showReason && (
          <label className="admin-modal-field">
            <span>Сообщение в боте</span>
            <textarea
              className="admin-modal-textarea"
              value={reason}
              onChange={(e) => onReasonChange?.(e.target.value)}
              placeholder={reasonPlaceholder}
              disabled={loading}
              rows={3}
            />
          </label>
        )}
        <div className="admin-modal-actions">
          <button
            type="button"
            className="panel-users-btn"
            data-modal-cancel
            disabled={loading}
            onClick={() => onCancel?.()}
          >
            {cancelText}
          </button>
          <button
            ref={confirmRef}
            type="button"
            className={`panel-users-btn${danger ? ' panel-users-btn-danger' : ' panel-users-btn-primary'}`}
            data-modal-confirm
            disabled={loading || !reasonOk}
            onClick={() => onConfirm?.()}
          >
            {loading ? '…' : confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}
