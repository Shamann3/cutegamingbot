import { useEffect, useState } from 'react'

export default function ItemGuideToastLayer() {
  const [toast, setToast] = useState(null)

  useEffect(() => {
    const handler = (event) => {
      const { name = 'Предмет', emoji = '📦' } = event.detail ?? {}
      setToast({ id: Date.now(), name, emoji })
    }
    window.addEventListener('farm:item-unavailable', handler)
    return () => window.removeEventListener('farm:item-unavailable', handler)
  }, [])

  useEffect(() => {
    if (!toast) return undefined
    const timer = setTimeout(() => {
      setToast((current) => (current?.id === toast.id ? null : current))
    }, 5000)
    return () => clearTimeout(timer)
  }, [toast])

  if (!toast) return null

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
