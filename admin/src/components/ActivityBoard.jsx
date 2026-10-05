import { useEffect, useState } from 'react'
import { fetchGroupActivity } from '../lib/adminClient'
import { watchLevel, watchLine } from '../lib/shiftDesk'
import { HabitGrid } from './sight/SightCharts'
import FocusWindow from './FocusWindow'

const PERIODS = [
  { id: 'day', label: 'Сегодня' },
  { id: 'week', label: '7 дней' },
  { id: 'month', label: 'Месяц' },
  { id: 'year', label: 'Год' },
]

const MONTHS = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']

function fmt(n) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  return new Intl.NumberFormat('ru-RU').format(Number(n))
}

function longLabel(iso, grain) {
  const parts = String(iso || '').split('-')
  const month = MONTHS[(Number(parts[1]) || 1) - 1] || ''
  if (grain === 'month') return `${month} ${parts[0] || ''}`.trim()
  return `${Number(parts[2]) || ''} ${month}`.trim()
}

function levelOf(value, max) {
  if (value == null || value <= 0 || max <= 0) return 0
  const t = value / max
  if (t < 0.25) return 1
  if (t < 0.5) return 2
  if (t < 0.75) return 3
  return 4
}

function ruTimes(count) {
  const n = Math.abs(Number(count) || 0)
  const n10 = n % 10
  const n100 = n % 100
  const word = n10 === 1 && n100 !== 11
    ? 'раз'
    : n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)
      ? 'раза'
      : 'раз'
  return `${n} ${word}`
}

function personNote(person, watch) {
  const row = (watch || []).find((item) => Number(item.userId) === Number(person.userId))
  const archive = person.times > 0
    ? `В архиве этого чата: ${ruTimes(person.times)}.`
    : 'В архиве этого чата его ещё нет.'
  const warns = row ? watchLine(watchLevel(row.warns), row.warns) : 'Активных предупреждений нет.'
  return `${archive} ${warns}`
}

function DayBars({ points = [], selected = '', onPick }) {
  const max = Math.max(...points.map((p) => Number(p.value) || 0), 1)
  return (
    <>
      <div className="act-bars" role="list" aria-label="Сообщения по дням">
        {points.map((point) => {
          const value = Number(point.value) || 0
          const on = selected && selected === point.date
          const h = Math.max(6, Math.round((value / max) * 100))
          return (
            <button
              key={point.date}
              type="button"
              role="listitem"
              className={on ? 'is-on' : ''}
              data-level={levelOf(value, max)}
              title={`${point.label}: ${fmt(value)} сообщений`}
              aria-label={`${point.label}: ${fmt(value)} сообщений`}
              aria-pressed={on}
              onClick={() => onPick?.(point.date)}
            >
              <i style={{ height: `${h}%` }} />
            </button>
          )
        })}
      </div>
      {points.length > 0 && points.length <= 10 && (
        <div className="grp-peak-days" aria-hidden="true">
          {points.map((point) => {
            const parts = String(point.date || '').split('-')
            const stamp = parts.length >= 3 ? `${Number(parts[2])}.${parts[1]}` : ''
            return <span key={point.date}>{stamp}</span>
          })}
        </div>
      )}
    </>
  )
}

export default function ActivityBoard({
  onOpenArchive,
  canArchive = false,
  chatId,
  repeats = new Map(),
  watch = [],
  seedPeriod = '',
  seedSlice = '',
}) {
  const [person, setPerson] = useState(null)
  const [period, setPeriod] = useState(seedPeriod || 'month')
  const [slice, setSlice] = useState(seedSlice || '')
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setSlice(seedSlice || '')
    setPeriod(seedPeriod || 'month')
    setReport(null)
    setPerson(null)
  }, [chatId, seedPeriod, seedSlice])

  useEffect(() => {
    if (!chatId) return undefined
    let stop = false
    setLoading(true)
    setError('')
    fetchGroupActivity(chatId, { period, slice })
      .then((data) => {
        if (!stop) setReport(data)
      })
      .catch((err) => {
        if (!stop) setError(err.message || 'Активность не открылась')
      })
      .finally(() => {
        if (!stop) setLoading(false)
      })
    return () => { stop = true }
  }, [chatId, period, slice])

  if (!chatId) {
    return <p className="realm-copy">Сначала выберите группу. Тогда здесь будут сообщения этого чата.</p>
  }

  const series = report?.series || []
  const focus = slice || report?.focus || ''
  const grain = report?.grain || (period === 'year' ? 'month' : 'day')
  const chartPoints = series.map((point) => ({
    date: point.date,
    label: longLabel(point.date, grain),
    value: Number(point.messages) || 0,
  }))
  const useBars = grain === 'day' && chartPoints.length > 0 && chartPoints.length <= 40

  return (
    <section className="act-board">
      <div className="realm-actions" role="tablist" aria-label="За какой срок показать сообщения">
        {PERIODS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={period === item.id ? 'is-on' : ''}
            onClick={() => { setPeriod(item.id); setSlice('') }}
          >
            {item.label}
          </button>
        ))}
      </div>
      {error && <p className="realm-alert" role="alert">{error}</p>}
      {loading && <p className="realm-copy">Считаем сообщения…</p>}
      {report && report.available === false && (
        <p className="realm-copy">Счётчик этого чата сейчас не открылся. Повторите позже. Нулей вместо живых цифр здесь нет.</p>
      )}
      {report && report.available !== false && (
        <>
          <div className="act-bento">
            <button type="button" className={slice ? '' : 'is-on'} onClick={() => setSlice('')}>
              <strong>{fmt(slice ? report.messages : report.periodMessages)}</strong>
              <span>{slice ? 'сообщений за этот день' : 'сообщений за выбранный срок'}</span>
            </button>
            <p>
              <strong>{fmt(slice ? report.writers : report.periodWriters)}</strong>
              <span>{slice ? 'писали в этот день' : 'писали за этот срок'}</span>
            </p>
          </div>
          <p className="realm-copy">
            {slice
              ? `${longLabel(focus, grain)}. Нажмите левую цифру, чтобы снова показать весь срок.`
              : `Прошлый такой же срок: ${fmt(report.previousMessages)} сообщений. Нажмите столбик — увидите один день.`}
          </p>
          {useBars ? (
            <DayBars
              points={chartPoints}
              selected={slice}
              onPick={(date) => setSlice(slice === date ? '' : date)}
            />
          ) : (
            <HabitGrid
              caption={grain === 'month' ? 'Сетка месяцев: светлее — больше сообщений.' : 'Сетка дней: светлее — больше сообщений.'}
              selected={slice}
              onPick={(date) => setSlice(slice === date ? '' : date)}
              points={chartPoints}
            />
          )}
          <h3 className="realm-h">Кто пишет</h3>
          <p className="realm-copy">Число справа — сообщения. Нажмите имя: откроется, сколько человек пишет и были ли наказания.</p>
          {(report.people || []).length === 0 && <p className="realm-copy">За этот срок никто не писал.</p>}
          <ul className="act-people">
            {(report.people || []).map((personRow, index) => {
              const times = repeats.get(Number(personRow.userId)) || 0
              const total = Number(slice ? report.messages : report.periodMessages) || 0
              const share = total > 0 ? Math.round((Number(personRow.messages) || 0) / total * 100) : 0
              return (
                <li key={personRow.userId} style={{ animationDelay: `${index * 40}ms` }}>
                  <button
                    type="button"
                    className="act-person"
                    aria-label={`${personRow.name}, ${fmt(personRow.messages)} сообщений. Открыть карточку`}
                    onClick={() => setPerson({ ...personRow, share, place: index + 1, times })}
                  >
                    <span className="act-person-main">
                      <strong>{personRow.name}</strong>
                      {personRow.username ? <span>@{String(personRow.username).replace(/^@/, '')}</span> : null}
                      <i className="act-person-track" aria-hidden="true">
                        <b style={{ width: `${Math.max(share, personRow.messages > 0 ? 4 : 0)}%` }} />
                      </i>
                    </span>
                    <b className="act-people-count">{fmt(personRow.messages)}</b>
                  </button>
                </li>
              )
            })}
          </ul>
          {person && (
            <FocusWindow
              title={person.name}
              subtitle={person.username ? `@${String(person.username).replace(/^@/, '')}` : `#${person.userId}`}
              onClose={() => setPerson(null)}
              footer={canArchive && onOpenArchive ? (
                <button
                  type="button"
                  className="sec-btn"
                  onClick={() => {
                    const id = person.userId
                    setPerson(null)
                    onOpenArchive(id)
                  }}
                >
                  Наказания этого человека
                </button>
              ) : null}
            >
              <div className="act-bento act-person-stats">
                <p>
                  <strong>{fmt(person.messages)}</strong>
                  <span>сообщений</span>
                </p>
                <p>
                  <strong>{person.share}%</strong>
                  <span>от всех сообщений за этот срок</span>
                </p>
                <p>
                  <strong>{person.place}</strong>
                  <span>место среди пишущих</span>
                </p>
              </div>
              <p className="realm-copy">{personNote(person, watch)}</p>
            </FocusWindow>
          )}
        </>
      )}
    </section>
  )
}
