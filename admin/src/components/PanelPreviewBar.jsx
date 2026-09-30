import { useEffect, useState } from 'react'

export default function PanelPreviewBar({ title, detail, onExit }) {
  const [blocked, setBlocked] = useState(false)

  useEffect(() => {
    let timer = 0
    const onBlocked = () => {
      setBlocked(true)
      window.clearTimeout(timer)
      timer = window.setTimeout(() => setBlocked(false), 2600)
    }
    window.addEventListener('epsilon-preview-blocked', onBlocked)
    return () => {
      window.removeEventListener('epsilon-preview-blocked', onBlocked)
      window.clearTimeout(timer)
    }
  }, [])

  return (
    <div className={`preview-bar${blocked ? ' is-blocked' : ''}`} role="region" aria-label="Копия панели">
      <p className="preview-bar-copy">
        <strong>{title}</strong>
        <span aria-live="polite">
          {blocked ? 'Действие не выполнено: в копии ничего не сохраняется' : detail}
        </span>
      </p>
      <button type="button" className="preview-bar-exit" onClick={onExit}>Выйти из копии</button>
    </div>
  )
}
