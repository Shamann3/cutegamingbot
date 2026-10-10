import { useEffect, useState } from 'react'

export function muteClock(iso) {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('ru-RU', {
    day: 'numeric',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function fieldOf(root, node) {
  if (!root || !node || !node.closest) return null
  const field = node.closest('input, textarea, [contenteditable="true"]')
  if (!field || !root.contains(field)) return null
  if (field.closest('.mute-lock')) return null
  if (field.disabled || field.readOnly) return null
  return field
}

export default function GroupMuteLock({ rootRef, lock }) {
  const [open, setOpen] = useState(false)
  const until = lock?.until || ''
  const group = lock?.group || 'этой группе'

  useEffect(() => {
    setOpen(false)
  }, [until, group])

  useEffect(() => {
    const root = rootRef?.current
    if (!root || !until) return undefined
    const stop = (event) => {
      const field = fieldOf(root, event.target)
      if (!field) return
      event.preventDefault()
      field.blur()
      setOpen(true)
    }
    root.addEventListener('focusin', stop)
    root.addEventListener('keydown', stop, true)
    return () => {
      root.removeEventListener('focusin', stop)
      root.removeEventListener('keydown', stop, true)
    }
  }, [rootRef, until])

  if (!until || !open) return null
  const when = muteClock(until)
  return (
    <div className="mute-lock" role="alertdialog" aria-modal="true" aria-labelledby="mute-lock-title">
      <div className="mute-lock-card">
        <strong id="mute-lock-title">Вас замутили</strong>
        <p>{when ? `до ${when}` : 'на текущий срок'}</p>
        <p>в группе «{group}»</p>
        <button type="button" onClick={() => setOpen(false)}>Понятно</button>
      </div>
    </div>
  )
}
