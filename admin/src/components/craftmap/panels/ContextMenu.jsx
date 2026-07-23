import { useEffect } from 'react'

export default function ContextMenu({ x, y, actions, onClose }) {
  useEffect(() => {
    const close = () => onClose()
    window.addEventListener('click', close)
    window.addEventListener('scroll', close, true)
    return () => {
      window.removeEventListener('click', close)
      window.removeEventListener('scroll', close, true)
    }
  }, [onClose])

  return (
    <div className="craftmap-ctx" style={{ left: x, top: y }} onClick={(e) => e.stopPropagation()}>
      {actions.map((a) => (
        <button key={a.label} type="button" onClick={() => { a.onClick(); onClose() }}>{a.label}</button>
      ))}
    </div>
  )
}
