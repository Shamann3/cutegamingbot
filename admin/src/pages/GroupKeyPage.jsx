import { useState } from 'react'
import { checkGroupKey } from '../lib/adminClient'
import { accentIsPersonal, loadStoredAccent } from '../lib/accentTheme'

export default function GroupKeyPage({ onBack, onPassed }) {
  const personal = accentIsPersonal(loadStoredAccent())
  const [key, setKey] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await checkGroupKey(key.trim())
      onPassed()
    } catch (err) {
      setError(err.message || 'Ключ не подошёл')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={`gate-root${personal ? ' is-personal' : ''}`}>
      <div className="gate-frame" aria-hidden="true" />
      <div className="gate-sheet">
        <header className="gate-head">
          <h1 className="gate-title">Личный ключ</h1>
          <p className="gate-lead">Из бота Telegram ключ не спрашивается. Здесь он нужен, потому что панель открыта без бота. Ключ выдаёт создатель при назначении, один раз.</p>
        </header>
        <form className="realm-form" onSubmit={submit}>
          <label>
            Ключ
            <input value={key} onChange={(e) => setKey(e.target.value)} autoComplete="off" />
          </label>
          {error && <p className="realm-alert" role="alert">{error}</p>}
          <button type="submit" className="realm-back" disabled={busy || key.trim().length < 8}>
            {busy ? 'Проверка…' : 'Открыть кабинет'}
          </button>
        </form>
        <button type="button" className="gate-text" onClick={onBack}>К дверям</button>
      </div>
    </div>
  )
}
