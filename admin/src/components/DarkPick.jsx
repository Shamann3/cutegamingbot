import { useEffect, useId, useRef, useState } from 'react'

/** Список внутри панели. Системное меню select на телефоне белое и не красится. */
export default function DarkPick({ label, value, placeholder = 'Выберите', options = [], onChange }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)
  const listId = useId()
  const current = options.find((item) => String(item.value) === String(value)) || null

  useEffect(() => {
    if (!open) return undefined
    const onPointer = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false)
    }
    const onKey = (event) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className={`dark-pick${open ? ' is-open' : ''}`} ref={rootRef}>
      {label ? <span className="dark-pick-label">{label}</span> : null}
      <button
        type="button"
        className="dark-pick-btn"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((next) => !next)}
      >
        <span>{current ? current.label : placeholder}</span>
        <i aria-hidden="true" />
      </button>
      {open && (
        <ul className="dark-pick-list" id={listId} role="listbox">
          {options.length === 0 && <li className="dark-pick-empty">Пока нечего выбрать</li>}
          {options.map((item) => {
            const on = String(item.value) === String(value)
            return (
              <li key={item.value}>
                <button
                  type="button"
                  role="option"
                  aria-selected={on}
                  className={on ? 'is-on' : ''}
                  onClick={() => {
                    onChange(String(item.value))
                    setOpen(false)
                  }}
                >
                  <strong>{item.label}</strong>
                  {item.hint ? <span>{item.hint}</span> : null}
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
