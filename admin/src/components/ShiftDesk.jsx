import { useEffect, useState } from 'react'
import CountUp from './CountUp'
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

export default function ShiftDesk({ chatId, canActivity, onOpen }) {
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

  const waiting = !report && !error
  const closed = report?.available === false
  const Hero = !waiting && !closed && onOpen ? 'button' : 'div'

  const story = tone === 'good'
    ? `Сообщений больше, чем ${meta.prev.toLowerCase()}: тогда было ${fmt(previous)}.`
    : tone === 'bad'
      ? `Сообщений меньше, чем ${meta.prev.toLowerCase()}: тогда было ${fmt(previous)}.`
      : tone === 'same'
        ? `Столько же сообщений, сколько ${meta.prev.toLowerCase()}: ${fmt(previous)}.`
        : 'Сообщения этого чата.'

  return (
    <section className="shift-desk grp-shift">
      <div className="dash-period e-seg" role="tablist" aria-label="За какой срок показать сообщения">
        {PERIODS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={period === item.id}
            className={period === item.id ? 'is-on' : ''}
            onClick={() => setPeriod(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {error && <p className="realm-alert" role="alert">{error}</p>}
      <Hero
        type={Hero === 'button' ? 'button' : undefined}
        className={`dash-bot-hero${waiting ? ' is-collecting' : ''}${onOpen && !waiting && !closed ? ' metric-tile' : ''} ${toneClass}`.trim()}
        aria-label={Hero === 'button' ? `${fmt(current)} сообщений. ${story}. Открыть, кто писал` : undefined}
        onClick={Hero === 'button' ? onOpen : undefined}
      >
        {waiting && (
          <span className="dash-collecting">
            <span className="dash-collecting-main">Считаем сообщения</span>
            <span className="dash-collecting-wait">этот чат</span>
          </span>
        )}
        {closed && <span className="dash-bot-hero-sub">Счётчик не открылся. Нули вместо живых цифр не ставятся.</span>}
        {!waiting && !closed && (
          <>
            <strong className="dash-bot-hero-value">
              <CountUp value={current} duration={520} />
            </strong>
            <span className="dash-bot-hero-sub">
              {story}
              {onOpen ? <span className="dash-bot-hero-more">Нажмите цифру — откроется, кто писал.</span> : null}
            </span>
          </>
        )}
      </Hero>
    </section>
  )
}
