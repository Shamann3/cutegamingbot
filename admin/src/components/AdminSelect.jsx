import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

export default function AdminSelect({
  value,
  onChange,
  options = [],
  disabled = false,
  placeholder = 'Выберите…',
  className = '',
}) {
  const [open, setOpen] = useState(false)
  const [menuStyle, setMenuStyle] = useState({})
  const rootRef = useRef(null)
  const triggerRef = useRef(null)
  const menuRef = useRef(null)

  // Позиционируем меню относительно триггера через getBoundingClientRect
  const updateMenuPosition = () => {
    if (!triggerRef.current) return
    const rect = triggerRef.current.getBoundingClientRect()
    const spaceBelow = window.innerHeight - rect.bottom
    const menuHeight = Math.min(224, options.length * 40 + 12) // ~40px per option
    const openUpward = spaceBelow < menuHeight + 8 && rect.top > menuHeight + 8

    setMenuStyle({
      position: 'fixed',
      zIndex: 13000,
      left: rect.left,
      width: rect.width,
      ...(openUpward
        ? { bottom: window.innerHeight - rect.top + 4 }
        : { top: rect.bottom + 4 }),
    })
  }

  useEffect(() => {
    if (!open) return undefined
    updateMenuPosition()

    const close = (event) => {
      const target = event.target
      if (!(target instanceof Node)) return
      // Меню висит на body, не внутри кнопки. Касание пункта не должно
      // закрывать список раньше клика — иначе нажатие падает в поле под ним.
      if (rootRef.current?.contains(target)) return
      if (menuRef.current?.contains(target)) return
      setOpen(false)
    }
    const reposition = () => updateMenuPosition()

    document.addEventListener('pointerdown', close, true)
    window.addEventListener('scroll', reposition, true)
    window.addEventListener('resize', reposition)
    return () => {
      document.removeEventListener('pointerdown', close, true)
      window.removeEventListener('scroll', reposition, true)
      window.removeEventListener('resize', reposition)
    }
  }, [open, options.length]) // eslint-disable-line

  const selected = options.find((opt) => opt.value === value)
  const displayLabel = selected?.label ?? placeholder

  const menu = open ? (
    <ul
      ref={menuRef}
      className="panel-select-menu"
      role="listbox"
      style={{ ...menuStyle, margin: 0 }}
      onPointerDown={(event) => event.stopPropagation()}
    >
      {options.length === 0 && (
        <li style={{ padding: '0.5rem 0.75rem', color: '#64748b', fontSize: '0.84rem' }}>
          Нет вариантов
        </li>
      )}
      {options.map((opt) => {
        const active = opt.value === value
        return (
          <li key={String(opt.value)} role="presentation">
            <button
              type="button"
              role="option"
              aria-selected={active}
              className={`panel-select-option${active ? ' panel-select-option-active' : ''}`}
              onClick={(event) => {
                event.preventDefault()
                event.stopPropagation()
                onChange(opt.value)
                setOpen(false)
              }}
            >
              {opt.label}
            </button>
          </li>
        )
      })}
    </ul>
  ) : null

  return (
    <div
      ref={rootRef}
      className={`panel-select${open ? ' panel-select-open' : ''}${disabled ? ' panel-select-disabled' : ''}${className ? ` ${className}` : ''}`}
    >
      <button
        ref={triggerRef}
        type="button"
        className="panel-select-trigger"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => {
          if (!disabled) setOpen((prev) => !prev)
        }}
      >
        <span className="panel-select-value">{displayLabel}</span>
        <span className="panel-select-chevron" aria-hidden />
      </button>

      {menu && createPortal(menu, document.body)}
    </div>
  )
}
