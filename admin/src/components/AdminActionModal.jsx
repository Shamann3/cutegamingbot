import { useEffect, useId, useRef, useState } from 'react'

const CLOSE_MS = 200

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
  showPassword = false,
  password = '',
  onPasswordChange,
  passwordHint = '',
  passwordRequired = false,
  onConfirm,
  onCancel,
}) {
  const titleId = useId()
  const dialogRef = useRef(null)
  const confirmRef = useRef(null)
  const [visible, setVisible] = useState(open)
  const [leaving, setLeaving] = useState(false)
  const reasonOk = !reasonRequired || String(reason || '').trim().length > 0
  const passwordOk = !passwordRequired || String(password || '').length > 0

  useEffect(() => {
    if (open) {
      setVisible(true)
      setLeaving(false)
      return undefined
    }
    if (!visible) return undefined
    setLeaving(true)
    const t = window.setTimeout(() => {
      setVisible(false)
      setLeaving(false)
    }, CLOSE_MS)
    return () => window.clearTimeout(t)
  }, [open, visible])

  useEffect(() => {
    if (!visible || leaving) return undefined
    const prev = document.activeElement
    const t = window.setTimeout(() => {
      if (showPassword) {
        dialogRef.current?.querySelector('input[type="password"]')?.focus()
      } else if (showReason) {
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
  }, [visible, leaving, showReason, showPassword])

  const requestClose = () => {
    if (loading || leaving) return
    onCancel?.()
  }

  if (!visible) return null

  return (
    <div
      className={`admin-modal-backdrop${leaving ? ' is-leaving' : ''}`}
      role="presentation"
      onClick={requestClose}
    >
      <div
        ref={dialogRef}
        className={`admin-modal${leaving ? ' is-leaving' : ''}`}
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
        {showPassword && (
          <label className="admin-modal-field">
            <span>Пароль{passwordHint ? ` · ${passwordHint}` : ''}</span>
            <input
              type="password"
              className="panel-users-input"
              value={password}
              onChange={(e) => onPasswordChange?.(e.target.value)}
              disabled={loading}
              autoComplete="off"
            />
          </label>
        )}
        <div className="admin-modal-actions">
          <button
            type="button"
            className="panel-users-btn"
            data-modal-cancel
            disabled={loading}
            onClick={requestClose}
          >
            {cancelText}
          </button>
          <button
            ref={confirmRef}
            type="button"
            className={`panel-users-btn${danger ? ' panel-users-btn-danger' : ' panel-users-btn-primary'}`}
            data-modal-confirm
            disabled={loading || !reasonOk || !passwordOk}
            onClick={() => onConfirm?.()}
          >
            {loading ? '…' : confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}
