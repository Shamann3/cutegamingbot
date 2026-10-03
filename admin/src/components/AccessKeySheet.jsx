import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

const LEAVE_MS = 240

function leaveDelay() {
  const media = window.matchMedia?.('(prefers-reduced-motion: reduce)')
  const light = document.body.classList.contains('perf-light')
  return media?.matches || light ? 0 : LEAVE_MS
}

const COPY = {
  staff: {
    off: 'Вход в панель сотрудника закроется сразу. Роль сохранится. Старый ключ больше не подойдёт — новый можно выдать, когда решите вернуть человека.',
    key: 'Человек снова сможет войти. Код из приложения останется, старые сессии закроются. Создатель сможет открыть этот ключ снова.',
  },
  group: {
    off: 'Кабинет закроется сразу. Должность в группе сохранится. Старый ключ больше не подойдёт — новый можно выдать позже.',
    key: 'Кабинет снова откроется этим ключом. Код из приложения останется. Создатель сможет открыть этот ключ снова.',
  },
}

export default function AccessKeySheet({
  open,
  name,
  kind = 'staff',
  step = 'off',
  busy = false,
  error = '',
  issuedKey = '',
  copy = '',
  onClose,
  onConfirm,
}) {
  const titleId = useId()
  const primaryRef = useRef(null)
  const [mounted, setMounted] = useState(open)
  const [leaving, setLeaving] = useState(false)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (open) {
      setMounted(true)
      setLeaving(false)
      setCopied(false)
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
    if (!open || !mounted) return undefined
    const onKey = (event) => {
      if (event.key === 'Escape' && !busy) onClose?.()
    }
    window.addEventListener('keydown', onKey)
    const focusTimer = window.setTimeout(() => primaryRef.current?.focus(), 30)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.clearTimeout(focusTimer)
    }
  }, [open, mounted, busy, step, onClose])

  if (!mounted) return null

  const place = COPY[kind] || COPY.staff
  const looking = step === 'look'
  const shown = step === 'shown' || (looking && Boolean(issuedKey))
  const title = looking ? 'Ключ' : shown ? 'Ключ готов' : step === 'key' ? 'Новый ключ' : 'Отключить доступ'
  const body = looking
    ? (issuedKey
      ? 'Этот ключ сейчас действует. Его можно открыть снова.'
      : (busy ? 'Открываем ключ…' : (error ? 'Ключ не открылся.' : (copy || 'Сейчас действующего ключа нет.'))))
    : shown
      ? 'Скопируйте ключ и передайте его лично. Создатель проекта сможет открыть его снова.'
      : (copy || place[step] || place.off)

  const copyKey = async () => {
    if (!issuedKey) return
    try {
      await navigator.clipboard.writeText(issuedKey)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return createPortal(
    <div className={`access-sheet${leaving ? ' is-leaving' : ''}`} role="presentation">
      <button
        type="button"
        className="access-sheet-veil"
        aria-label="Закрыть"
        disabled={busy}
        onClick={() => { if (!busy) onClose?.() }}
      />
      <div
        className="access-sheet-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <p className="access-sheet-kicker">{kind === 'group' ? 'Администратор' : 'Сотрудник'}</p>
        <h2 id={titleId} className="access-sheet-title">{title}</h2>
        {name ? <p className="access-sheet-name">{name}</p> : null}
        <p className="access-sheet-copy">{body}</p>
        {shown && issuedKey ? (
          <div className="access-key" data-copyable="1">
            <code>{issuedKey}</code>
          </div>
        ) : null}
        {error ? <p className="access-sheet-error" role="alert">{error}</p> : null}
        <div className="access-sheet-actions">
          {shown || looking ? (
            <>
              {issuedKey ? (
                <button
                  ref={primaryRef}
                  type="button"
                  className="sec-btn sec-btn-sm"
                  onClick={copyKey}
                >
                  {copied ? 'Скопировано' : 'Скопировать'}
                </button>
              ) : null}
              <button
                ref={issuedKey ? undefined : primaryRef}
                type="button"
                className="sec-btn sec-btn-ghost sec-btn-sm"
                disabled={busy}
                onClick={onClose}
              >
                Готово
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className="sec-btn sec-btn-ghost sec-btn-sm"
                disabled={busy}
                onClick={onClose}
              >
                Оставить как есть
              </button>
              <button
                ref={primaryRef}
                type="button"
                className={`sec-btn sec-btn-sm${step === 'off' ? ' sec-btn-danger' : ' sec-btn-success'}`}
                disabled={busy}
                onClick={onConfirm}
              >
                {busy ? 'Секунду…' : step === 'key' ? 'Выдать ключ' : 'Отключить'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}
