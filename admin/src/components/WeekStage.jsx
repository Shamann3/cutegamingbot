import CountUp from './CountUp'

const WEEKDAYS = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб']

function fmt(n) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  return new Intl.NumberFormat('ru-RU').format(Number(n))
}

function partsOf(iso) {
  const parts = String(iso || '').split('-')
  if (parts.length < 3) return { day: '', stamp: '' }
  const date = new Date(`${parts[0]}-${parts[1]}-${parts[2]}T12:00:00`)
  const day = Number.isNaN(date.getTime()) ? '' : WEEKDAYS[date.getDay()]
  return { day, stamp: `${Number(parts[2])}.${parts[1]}` }
}

/** Неделя столбиками: высота — сообщения, цифра сверху, день снизу. */
export default function WeekStage({ points = [], active = '', onPick }) {
  const values = points.map((point) => Number(point.messages) || 0)
  const max = Math.max(...values, 1)
  const total = values.reduce((sum, value) => sum + value, 0)
  const peakAt = values.reduce((best, value, index) => (value > values[best] ? index : best), 0)
  const peak = points[peakAt]
  const peakParts = peak ? partsOf(peak.date) : null
  const peakLine = peak && values[peakAt] > 0
    ? `Выше всех — ${peakParts.day} ${peakParts.stamp}, ${fmt(values[peakAt])}.`
    : ''

  return (
    <div className="week-stage">
      <div className="week-stage-head">
        <h3 className="realm-h">Сообщения за неделю</h3>
        <p className="week-stage-total">
          <b><CountUp value={total} duration={720} /></b>
          <span>за эти дни</span>
        </p>
      </div>
      <p className="realm-copy">Нажмите день — кто писал, откроется ниже, на этой странице.</p>
      {peakLine && <p className="week-peak">{peakLine}</p>}
      <div className="week-plot" role="list" aria-label="Сообщения по дням недели">
        {points.map((point, index) => {
          const value = Number(point.messages) || 0
          const ratio = value <= 0 ? 0.06 : Math.max(0.1, value / max)
          const { day, stamp } = partsOf(point.date)
          const on = active === point.date
          const peakDay = value > 0 && index === peakAt
          return (
            <button
              key={point.date || index}
              type="button"
              role="listitem"
              className={`week-col${on ? ' is-on' : ''}${peakDay ? ' is-peak' : ''}`}
              style={{ '--rise': ratio, '--i': index }}
              aria-pressed={on}
              aria-label={`${day} ${stamp}: ${fmt(value)} сообщений`}
              onClick={() => onPick?.(point)}
            >
              <span className="week-count">{fmt(value)}</span>
              <span className="week-track" aria-hidden="true">
                <span className="week-fill" />
              </span>
              <span className="week-name">{day}</span>
              <span className="week-date">{stamp}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
