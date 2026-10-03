import { useEffect, useState } from 'react'
import { clearGroupEntry, readGroupEntry, rememberGroupEntry, resumeGroupEntry } from '../lib/adminClient'
import { accentIsPersonal, loadStoredAccent } from '../lib/accentTheme'
import EntryFrame from '../components/EntryFrame'

function broken(err) {
  return err?.status === 401 || err?.status === 403
}

export default function GroupResume({ onBack, onPassed, onAskKey }) {
  const personal = accentIsPersonal(loadStoredAccent())
  const [note, setNote] = useState('')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let alive = true
    const pass = readGroupEntry()
    if (!pass) {
      onAskKey('')
      return undefined
    }
    setNote('')
    resumeGroupEntry(pass)
      .then((data) => {
        if (!alive) return
        if (data?.entryPass) rememberGroupEntry(data.entryPass)
        onPassed()
      })
      .catch((err) => {
        if (!alive) return
        if (broken(err)) {
          clearGroupEntry()
          onAskKey(err?.message || 'Напишите ключ ещё раз.')
          return
        }
        setNote('Сервер не ответил. Кабинет откроется, когда он ответит.')
      })
    return () => { alive = false }
  }, [attempt, onAskKey, onPassed])

  return (
    <EntryFrame
      title="Панель администратора"
      lead="Узнаём, кто входит."
      personal={personal}
      onBack={onBack}
    >
      {note ? (
        <>
          <p className="auth-message auth-message-error" role="alert">{note}</p>
          <button type="button" className="auth-btn auth-btn-primary" onClick={() => setAttempt((n) => n + 1)}>
            Открыть ещё раз
          </button>
        </>
      ) : (
        <p className="auth-checking">
          <span className="auth-spinner" aria-hidden="true" />
          Открываем кабинет…
        </p>
      )}
    </EntryFrame>
  )
}
