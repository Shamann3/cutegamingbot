import { useEffect, useId, useState } from 'react'
import { createPortal } from 'react-dom'
import { fetchMyDoorKeys, isPanelPreviewMode } from '../lib/adminClient'
import { doorKeyLine } from '../lib/doorKeys'

const DOORS = [
  { id: 'staff', title: 'Панель сотрудника' },
  { id: 'group', title: 'Панель администратора' },
]

function KeyBlock({ door, pack, copied, onCopy }) {
  const ready = pack?.state === 'ready' && pack.key
  return (
    <section className="own-key-block">
      <h3>{door.title}</h3>
      {ready ? (
        <>
          <div className="access-key" data-copyable="1">
            <code>{pack.key}</code>
          </div>
          <button type="button" className="sec-btn sec-btn-sm" onClick={() => onCopy(door.id, pack.key)}>
            {copied === door.id ? 'Скопировано' : 'Скопировать'}
          </button>
        </>
      ) : (
        <p>{doorKeyLine(door.id, pack?.state)}</p>
      )}
    </section>
  )
}

function OwnKeySheet({ open, onClose }) {
  const titleId = useId()
  const [pack, setPack] = useState(null)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState('')

  useEffect(() => {
    if (!open) return undefined
    let stop = false
    setPack(null)
    setError('')
    setCopied('')
    fetchMyDoorKeys()
      .then((data) => {
        if (!stop) setPack(data)
      })
      .catch((err) => {
        if (!stop) setError(err?.message || 'Ключ не открылся')
      })
    return () => { stop = true }
  }, [open])

  useEffect(() => {
    if (!open) return undefined
    const onKey = (event) => {
      if (event.key === 'Escape') onClose?.()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const copyKey = async (id, value) => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(id)
    } catch {
      setCopied('')
    }
  }

  return createPortal(
    <div className="access-sheet" role="presentation">
      <button type="button" className="access-sheet-veil" aria-label="Закрыть" onClick={onClose} />
      <div className="access-sheet-card" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <h2 id={titleId} className="access-sheet-title">Мой ключ</h2>
        <p className="access-sheet-copy">
          Им вы входите снова. Открывается и тогда, когда вы уже внутри. Никому его не отправляйте.
        </p>
        {error ? <p className="access-sheet-error" role="alert">{error}</p> : null}
        {!pack && !error ? <p className="access-sheet-copy">Открываем ваши ключи…</p> : null}
        {pack ? DOORS.map((door) => (
          <KeyBlock
            key={door.id}
            door={door}
            pack={pack[door.id]}
            copied={copied}
            onCopy={copyKey}
          />
        )) : null}
        <div className="access-sheet-actions">
          <button type="button" className="sec-btn sec-btn-ghost sec-btn-sm" onClick={onClose}>
            Готово
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}

export default function OwnKeyControl({ variant = 'row' }) {
  const [open, setOpen] = useState(false)
  if (isPanelPreviewMode()) return null

  const openSheet = () => setOpen(true)

  return (
    <>
      {variant === 'sidebar' ? (
        <button type="button" className="panel-logout-btn" onClick={openSheet}>
          Мой ключ
          <span className="panel-logout-hint">открыть, уже находясь внутри</span>
        </button>
      ) : variant === 'inline' ? (
        <button type="button" className="sec-btn sec-btn-ghost sec-btn-sm" onClick={openSheet}>
          Мой ключ
        </button>
      ) : (
        <button type="button" className="pocket-tools-row" onClick={openSheet}>
          <strong>Мой ключ</strong>
          <span>Ключ входа. Можно открыть, уже находясь внутри</span>
        </button>
      )}
      <OwnKeySheet open={open} onClose={() => setOpen(false)} />
    </>
  )
}
