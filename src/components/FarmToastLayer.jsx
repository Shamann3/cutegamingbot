function ToastItems({ items, sign }) {
  return (
    <div className="farm-toast-lines">
      {items.map((item) => (
        <span key={`${item.itemId}-${item.amount}`} className="farm-toast-line">
          <span className="farm-toast-sign" aria-hidden>{sign}</span>
          <span className="farm-toast-amount">{item.amount}</span>
          <span className="farm-toast-emoji" aria-hidden>{item.emoji || '📦'}</span>
          <span className="farm-toast-name">{item.name}</span>
        </span>
      ))}
    </div>
  )
}

function ToastStack({ toasts, variant, title }) {
  if (!toasts?.length) return null
  const sign = variant === 'gain' ? '+' : '−'
  return (
    <>
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`farm-toast farm-toast--${variant}`}
          role="status"
          aria-live="polite"
        >
          <span className="farm-toast-title">{title}</span>
          <ToastItems items={toast.items} sign={sign} />
        </div>
      ))}
    </>
  )
}

export default function FarmToastLayer({ gainToasts = [], spendToasts = [] }) {
  if (!gainToasts.length && !spendToasts.length) return null

  return (
    <div className="farm-toast-layer" aria-label="Уведомления фермы">
      <ToastStack toasts={gainToasts} variant="gain" title="Получено" />
      <ToastStack toasts={spendToasts} variant="spend" title="Потрачено" />
    </div>
  )
}
