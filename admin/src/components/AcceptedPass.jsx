import { useEffect, useState } from 'react'

const COPY = {
  staff: {
    kicker: 'Панель сотрудника',
    title: 'Заявка принята',
    steps: [
      'Создатель уже открыл вам вход.',
      'Дальше вкладка «Вход».',
      'Тот же ключ, затем шесть цифр из приложения.',
    ],
    action: 'Открыть вход',
  },
  group: {
    kicker: 'Панель администратора',
    title: 'Заявка принята',
    steps: [
      'Должность ваша. Ключ ниже и в сообщении бота.',
      'Откройте вход панели администратора.',
      'Вставьте ключ, затем шесть цифр из приложения.',
    ],
    action: 'Открыть вход',
  },
}

function motionOff() {
  if (typeof window === 'undefined') return true
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return true
  return document.body.classList.contains('perf-light')
}

export default function AcceptedPass({ kind = 'staff', onAction, children }) {
  const copy = COPY[kind] || COPY.staff
  const [shown, setShown] = useState(() => (motionOff() ? copy.steps.length : 0))

  useEffect(() => {
    if (motionOff()) {
      setShown(copy.steps.length)
      return undefined
    }
    setShown(0)
    const timers = copy.steps.map((_, index) => window.setTimeout(() => {
      setShown(index + 1)
    }, 220 + index * 380))
    return () => timers.forEach((timer) => window.clearTimeout(timer))
  }, [kind, copy.steps])

  return (
    <div className="accept-pass" role="status">
      <p className="accept-kicker">{copy.kicker}</p>
      <h2 className="accept-title">{copy.title}</h2>
      <ol className="accept-steps">
        {copy.steps.map((step, index) => (
          <li key={step} className={index < shown ? 'is-on' : ''} style={{ '--step': index }}>
            <span className="accept-index">{index + 1}</span>
            <span>{step}</span>
          </li>
        ))}
      </ol>
      {children}
      <button type="button" className="auth-btn auth-btn-primary" onClick={onAction}>
        {copy.action}
      </button>
    </div>
  )
}
