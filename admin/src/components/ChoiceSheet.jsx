import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

const LEAVE_MS = 220

function leaveDelay() {
  const media = window.matchMedia?.('(prefers-reduced-motion: reduce)')
  return media?.matches ? 0 : LEAVE_MS
}

export default function ChoiceSheet({
  prompt,
  value,
  options,
  onChange,
  open,
  onOpen,
  onClose,
  placeholder = 'Открыть список',
}) {
  const titleId = useId()
  const listRef = useRef(null)
  const [mounted, setMounted] = useState(open)
  const [leaving, setLeaving] = useState(false)
  const selected = options.find((item) => item.id === value) || null

  const settle = (action) => (event) => {
    event.preventDefault()
    event.stopPropagation()
    window.setTimeout(action, 0)
  }

  useEffect(() => {
    if (open) {
      setMounted(true)
      setLeaving(false)
      return undefined
    }
    if (!mounted) return undefined
    setLeaving(true)
    const timer = window.setTimeout(() => {
      setMounted(false)
      setLeaving(false)
    }, leaveDelay())
    return () => window.clearTimeout(timer)
  }, [open, mounted])

  useEffect(() => {
    if (!mounted || leaving) return undefined
    const onKey = (event) => {
      if (event.key === 'Escape') onClose()
      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
      const buttons = [...(listRef.current?.querySelectorAll('button') || [])]
      if (!buttons.length) return
      event.preventDefault()
      const index = buttons.indexOf(document.activeElement)
      const next = event.key === 'ArrowDown'
        ? buttons[(index + 1 + buttons.length) % buttons.length]
        : buttons[(index - 1 + buttons.length) % buttons.length]
      next.focus()
    }
    document.addEventListener('keydown', onKey)
    const current = listRef.current?.querySelector('.is-selected') || listRef.current?.querySelector('button')
    current?.focus()
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [mounted, leaving, onClose])

  return (
    <div className="choice-field">
      <p className="auth-form-lead">{prompt}</p>
      <button
        type="button"
        className={`choice-trigger${selected ? ' is-set' : ''}`}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={onOpen}
      >
        <span>{selected ? selected.label : placeholder}</span>
      </button>
      {mounted && createPortal(
        <div className={`choice-layer${leaving ? ' is-leaving' : ''}`} onClick={settle(onClose)}>
          <div className="choice-dim" />
          <div
            className="choice-sheet"
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            onClick={(event) => event.stopPropagation()}
          >
            <p id={titleId} className="choice-sheet-title">{prompt}</p>
            <div className="choice-sheet-list" ref={listRef}>
              {options.map((item) => {
                const active = item.id === value
                return (
                  <button
                    key={item.id}
                    type="button"
                    className={`choice-option${active ? ' is-selected' : ''}`}
                    aria-pressed={active}
                    onClick={settle(() => onChange(item.id))}
                  >
                    <span>{item.label}</span>
                  </button>
                )
              })}
            </div>
            <button type="button" className="choice-close" onClick={settle(onClose)}>
              Закрыть
            </button>
          </div>
        </div>,
        document.body,
      )}
    </div>
  )
}
