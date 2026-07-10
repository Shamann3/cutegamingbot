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
  if (!open) return null

  const reasonOk = !reasonRequired || String(reason || '').trim().length > 0

  return (
    <div
      className="admin-modal-backdrop"
      role="presentation"
      onClick={() => {
        if (!loading) onCancel?.()
      }}
    >
      <div
        className="admin-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="admin-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 id="admin-modal-title" className="admin-modal-title">
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
            disabled={loading}
            onClick={() => onCancel?.()}
          >
            {cancelText}
          </button>
          <button
            type="button"
            className={`panel-users-btn${danger ? ' panel-users-btn-danger' : ' panel-users-btn-primary'}`}
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
