import { showToast } from './ToastHost'

function at(name) {
  const raw = String(name || '').trim()
  if (!raw) return ''
  return raw.startsWith('@') ? raw : `@${raw}`
}

export async function copyValue(text, ok = 'Скопировано') {
  const value = String(text ?? '').trim()
  if (!value) return false
  try {
    await navigator.clipboard.writeText(value)
    showToast(ok)
    return true
  } catch {
    showToast('Не скопировалось', 'error')
    return false
  }
}

export default function Copyable({ value, label, children, className = '' }) {
  const text = String(value ?? '').trim()
  if (!text) return null

  const onActivate = async (event) => {
    const sel = window.getSelection?.()
    if (sel && !sel.isCollapsed && event.currentTarget.contains(sel.anchorNode)) return
    event.preventDefault()
    event.stopPropagation()
    await copyValue(text, label ? `${label} скопирован` : 'Скопировано')
  }

  return (
    <span
      className={`panel-copyable${className ? ` ${className}` : ''}`}
      data-copyable="1"
      data-copy-value={text}
      title="Можно выделить или нажать — скопируется"
      onClick={onActivate}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onActivate(event)
        }
      }}
      role="button"
      tabIndex={0}
    >
      {children ?? text}
    </span>
  )
}

export function CopyableId({ value, label = 'id' }) {
  const text = String(value ?? '').trim()
  if (!text) return null
  return <Copyable value={text} label={label}>{label} {text}</Copyable>
}

export function CopyableUsername({ value, label = 'username' }) {
  const text = at(value)
  if (!text || text === '@') return null
  return <Copyable value={text} label={label}>{text}</Copyable>
}
