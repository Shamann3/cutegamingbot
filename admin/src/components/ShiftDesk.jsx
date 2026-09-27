import { useEffect, useState } from 'react'
import { fetchGroupActivity } from '../lib/adminClient'
import { compareTone } from '../lib/shiftDesk'

const PERIODS = [
  { id: 'day', label: 'День', now: 'Сегодня', prev: 'Вчера' },
  { id: 'month', label: 'Месяц', now: 'Этот месяц', prev: 'Прошлый месяц' },
  { id: 'year', label: 'Год', now: 'Этот год', prev: 'Прошлый год' },
]

function fmt(n) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  return new Intl.NumberFormat('ru-RU').format(Number(n))
}

export default function ShiftDesk({ chatId, canActivity }) {
  const [period, setPeriod] = useState('day')
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!chatId || !canActivity) return undefined
    let stop = false
    setError('')
    fetchGroupActivity(chatId, { period })
      .then((data) => { if (!stop) setReport(data) })
      .catch((err) => { if (!stop) setError(err.message || 'Счётчик не открылся') })
    return () => { stop = true }
  }, [chatId, canActivity, period])

  if (!chatId || !canActivity) return null

  const meta = PERIODS.find((item) => item.id === period) || PERIODS[0]
  const current = report?.available === false ? null : report?.periodMessages
  const previous = report?.available === false ? null : report?.previousMessages
  const tone = compareTone(current, previous)
  const toneClass = tone === 'good' ? 'is-good' : tone === 'bad' ? 'is-bad' : ''

  return (
    <section className="shift-desk">
      <div className="realm-actions" aria-label="Период сообщений">
        {PERIODS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={period === item.id ? 'is-on' : ''}
            onClick={() => setPeriod(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {error && <p className="realm-alert" role="alert">{error}</p>}
      {report?.available === false && (
        <p className="realm-copy">Счётчик не открылся. Вместо живых цифр нули не ставятся.</p>
      )}
      <div className="act-figures">
        <p className={toneClass}>
          <strong>{fmt(current)}</strong>
          <span>{meta.now}</span>
        </p>
        <p>
          <strong>{fmt(previous)}</strong>
          <span>{meta.prev}</span>
        </p>
      </div>
      <p className="realm-copy">Зелёный — сообщений больше, чем в прошлый раз. Красный — меньше. Поровну цвет не меняется.</p>
    </section>
  )
}
