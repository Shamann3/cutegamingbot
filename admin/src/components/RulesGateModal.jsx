import { useEffect, useState } from 'react'
import { acceptStaffRules } from '../lib/adminClient'
import { RULES_SECTIONS, RULES_TIMER_SECONDS } from '../config/rulesText'

function fmtTimer(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

export default function RulesGateModal({ onAccepted }) {
  const [remaining, setRemaining] = useState(RULES_TIMER_SECONDS)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Обратный отсчёт
  useEffect(() => {
    if (remaining <= 0) return undefined
    const id = window.setInterval(() => {
      setRemaining((prev) => (prev <= 1 ? 0 : prev - 1))
    }, 1000)
    return () => window.clearInterval(id)
  }, [remaining])

  // Блокируем Esc и скролл фона
  useEffect(() => {
    const blockKeys = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        e.stopPropagation()
      }
    }
    document.addEventListener('keydown', blockKeys, true)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', blockKeys, true)
      document.body.style.overflow = prevOverflow
    }
  }, [])

  const unlocked = remaining <= 0

  const handleAccept = async () => {
    if (!unlocked || loading) return
    setError('')
    setLoading(true)
    try {
      await acceptStaffRules()
      onAccepted()
    } catch (err) {
      setError(err?.message || 'Не удалось подтвердить. Попробуйте ещё раз')
      setLoading(false)
    }
  }

  return (
    <div className="rules-gate-backdrop" role="dialog" aria-modal="true">
      <div className="rules-gate">
        <header className="rules-gate-header">
          <h2 className="rules-gate-title">Правила работы</h2>
          <p className="rules-gate-sub">Прочитай внимательно. Это обязательно для допуска к панели.</p>
        </header>

        <div className="rules-gate-body">
          {RULES_SECTIONS.map((section, i) => (
            <section className="rules-gate-section" key={i}>
              {section.title && <h3 className="rules-gate-section-title">{section.title}</h3>}
              {section.paragraphs.map((p, j) => (
                <p className="rules-gate-text" key={j}>{p}</p>
              ))}
            </section>
          ))}
        </div>

        <footer className="rules-gate-footer">
          {error && <p className="rules-gate-error">{error}</p>}
          {!unlocked ? (
            <p className="rules-gate-timer">
              Кнопка станет активной через {fmtTimer(remaining)}…
            </p>
          ) : null}
          <button
            type="button"
            className="rules-gate-btn"
            disabled={!unlocked || loading}
            onClick={handleAccept}
          >
            {loading ? 'Подтверждение…' : 'Согласен и приступаю'}
          </button>
        </footer>
      </div>
    </div>
  )
}
