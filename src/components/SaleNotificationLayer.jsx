import { useNotifications } from '../hooks/useNotifications'

function SaleToast({ toast, onDismiss }) {
  const kindClass = toast.kind === 'market_sale' ? 'sale-toast-market' : 'sale-toast-generic'

  return (
    <div
      className={`sale-toast ${kindClass}${toast.entering ? ' sale-toast-enter' : ''}${toast.leaving ? ' sale-toast-leave' : ''}`}
      role="status"
      aria-live="polite"
    >
      <div className="sale-toast-glow" aria-hidden />
      <div className="sale-toast-sparkles" aria-hidden>
        <span />
        <span />
        <span />
      </div>
      <button
        type="button"
        className="sale-toast-dismiss"
        aria-label="Закрыть"
        onClick={() => onDismiss(toast.id)}
      >
        ×
      </button>
      <div className="sale-toast-icon" aria-hidden>
        {toast.kind === 'market_sale' ? '💰' : '🔔'}
      </div>
      <div className="sale-toast-content">
        <p className="sale-toast-title">{toast.title}</p>
        <p className="sale-toast-body">{toast.body}</p>
        {toast.detail ? <p className="sale-toast-detail">{toast.detail}</p> : null}
      </div>
    </div>
  )
}

export default function SaleNotificationLayer() {
  const { toasts, dismissToast } = useNotifications()

  if (!toasts.length) return null

  return (
    <div className="sale-toast-stack" aria-label="Уведомления о продажах">
      {toasts.map((toast) => (
        <SaleToast key={toast.id} toast={toast} onDismiss={dismissToast} />
      ))}
    </div>
  )
}
