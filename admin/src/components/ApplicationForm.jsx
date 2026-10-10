import { useEffect, useMemo, useState } from 'react'
import AdminSelect from './AdminSelect'
import { APPLICATION_QUESTIONS, PAYOUT_OPTIONS } from '../config/applicationQuestions'
import { fetchApplicationQuestions } from '../lib/adminClient'
import { APPLY_MAX, applyHint, applyReady } from '../lib/applyLimits'
import { playMeme } from '../lib/memeSounds'

// Нормализует вопрос из БД (поле key) или статического списка (поле id) к единому виду
function normalizeQuestion(q) {
  return { ...q, id: q.key || q.id }
}

// Дедуплицирует по id, оставляя первое вхождение
function deduplicateById(list) {
  const seen = new Set()
  return list.filter((q) => {
    if (seen.has(q.id)) return false
    seen.add(q.id)
    return true
  })
}

export default function ApplicationForm({ onSubmit, loading, error, info }) {
  const [answers, setAnswers] = useState({})
  const [questions, setQuestions] = useState(() => deduplicateById(APPLICATION_QUESTIONS.map(normalizeQuestion)))

  useEffect(() => {
    playMeme('useful')
  }, [])

  useEffect(() => {
    let cancelled = false
    fetchApplicationQuestions()
      .then((d) => {
        if (!cancelled && Array.isArray(d.items) && d.items.length) {
          setQuestions(deduplicateById(d.items.map(normalizeQuestion)))
        }
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

  const setAnswer = (id, value) => {
    setAnswers((prev) => ({ ...prev, [id]: value }))
  }

  const canSubmit = useMemo(() => {
    return questions.every((q) => {
      const value = String(answers[q.id] || '').trim()
      if (q.type === 'textarea') return q.required ? applyReady(value) : value === '' || applyReady(value)
      return !q.required || value.length > 0
    })
  }, [answers, questions])

  const handleSubmit = (event) => {
    event.preventDefault()
    if (!canSubmit) return
    const cleaned = {}
    for (const q of questions) {
      const value = (answers[q.id] || '').trim()
      if (value) cleaned[q.id] = value
    }
    onSubmit({
      answers: cleaned,
      payoutType: 'other',
      payoutDetails: '',
    })
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit}>
      <p className="auth-form-lead">
        Длинный ответ — от 50 до 2000 символов. Короткий можно написать как есть. Создатель решит, пускать ли вас.
      </p>

      {questions.map((q) => (
        <label className="auth-field" key={q.id}>
          <span className="auth-label">{q.label}</span>
          {q.type === 'textarea' ? (
            <>
              <textarea
                className="auth-input auth-textarea"
                rows={4}
                maxLength={APPLY_MAX}
                placeholder={q.placeholder || 'От 50 до 2000 символов'}
                value={answers[q.id] || ''}
                onChange={(event) => setAnswer(q.id, event.target.value)}
                required={q.required}
              />
              <p className="apply-hint">{applyHint(answers[q.id] || '', !q.required)}</p>
            </>
          ) : (
            <input
              className="auth-input"
              type="text"
              autoComplete="off"
              maxLength={200}
              placeholder={q.placeholder || ''}
              value={answers[q.id] || ''}
              onChange={(event) => setAnswer(q.id, event.target.value)}
              required={q.required}
            />
          )}
        </label>
      ))}

      {info && <p className="auth-message auth-message-info">{info}</p>}
      {error && <p className="auth-message auth-message-error">{error}</p>}

      <button
        type="submit"
        className="auth-btn auth-btn-primary"
        disabled={loading || !canSubmit}
      >
        {loading ? 'Отправка…' : 'Подать заявку'}
      </button>
    </form>
  )
}
