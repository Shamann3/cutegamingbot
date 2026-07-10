import { useEffect, useState } from 'react'

// Глобальный показ тоста: showToast('Готово') или showToast('Ошибка', 'error')
export function showToast(message, kind = 'success') {
  window.dispatchEvent(new CustomEvent('admin-toast', { detail: { message, kind } }))
}

let idSeq = 1

export default function ToastHost() {
  const [toasts, setToasts] = useState([])

  useEffect(() => {
    const onToast = (e) => {
      const id = idSeq++
      const { message, kind } = e.detail || {}
      setToasts((prev) => [...prev, { id, message, kind, leaving: false }])
      window.setTimeout(() => {
        setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, leaving: true } : t)))
      }, 3200)
      window.setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id))
      }, 3550)
    }
    window.addEventListener('admin-toast', onToast)
    return () => window.removeEventListener('admin-toast', onToast)
  }, [])

  if (toasts.length === 0) return null

  return (
    <div className="toast-host" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast toast-${t.kind === 'error' ? 'error' : 'success'}${t.leaving ? ' toast-out' : ''}`}>
          <i className="toast-icon" aria-hidden="true">{t.kind === 'error' ? '✕' : '✓'}</i>
          <span>{t.message}</span>
        </div>
      ))}
    </div>
  )
}
