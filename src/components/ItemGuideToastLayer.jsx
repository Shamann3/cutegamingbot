import { useEffect, useState } from 'react'

export default function ItemGuideToastLayer() {
  const [toast, setToast] = useState(null)

  useEffect(() => {
    const onMiss = (event) => {
      const { name = 'Предмет', emoji = '📦' } = event.detail ?? {}
      setToast({
        id: Date.now(),
        kind: 'miss',
        name,
        emoji,
      })
    }
    const onBought = (event) => {
      const {
        name = 'Предмет',
        emoji = '🌱',
        quantity = 1,
      } = event.detail ?? {}
      setToast({
        id: Date.now(),
        kind: 'bought',
        name,
        emoji,
        quantity,
      })
    }
    window.addEventListener('farm:item-unavailable', onMiss)
    window.addEventListener('farm:purchase-complete', onBought)
    return () => {
      window.removeEventListener('farm:item-unavailable', onMiss)
      window.removeEventListener('farm:purchase-complete', onBought)
    }
  }, [])

  useEffect(() => {
    if (!toast) return undefined
    const timer = setTimeout(() => {
      setToast((current) => (current?.id === toast.id ? null : current))
    }, toast.kind === 'bought' ? 3200 : 5000)
    return () => clearTimeout(timer)
  }, [toast])

  if (!toast) return null

  if (toast.kind === 'bought') {
    return (
      <div className="item-guide-toast-layer" role="status" aria-live="polite">
        <div className="item-guide-hint item-guide-hint--ok">
          <div className="item-guide-hint-head">
            <span className="item-guide-hint-emoji" aria-hidden>{toast.emoji}</span>
            <div className="item-guide-hint-copy">
              <p className="item-guide-hint-title">Куплено</p>
              <p className="item-guide-hint-body">
                «
                <strong>{toast.name}</strong>
                »
                {toast.quantity > 1 ? ` ×${toast.quantity}` : ''}
                {' '}
                — можно сажать на пустой грядке
              </p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="item-guide-toast-layer" role="status" aria-live="polite">
      <div className="item-guide-hint item-guide-hint--miss">
        <div className="item-guide-hint-head">
          <span className="item-guide-hint-emoji" aria-hidden>{toast.emoji}</span>
          <div className="item-guide-hint-copy">
            <p className="item-guide-hint-title">В магазине нет</p>
            <p className="item-guide-hint-body">
              В официальном магазине нет «
              <strong>{toast.name}</strong>
              ». Попробуйте купить предмет на бирже или найдите у других игроков лично.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
