import { useEffect, useState } from 'react'
import { fetchGroupActivity } from '../lib/adminClient'
import { watchLevel, watchLine } from '../lib/shiftDesk'
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

function pctChange(now, before) {
  const current = Number(now)
  const past = Number(before)
  if (!Number.isFinite(current) || !Number.isFinite(past) || past <= 0) return null
  return Math.round(((current - past) / past) * 100)
}

function compareSentence(now, before, noun) {
  if (before == null || now == null) return `${noun}: прошлый срок не посчитался.`
  const current = Number(now)
  const past = Number(before)
  if (!Number.isFinite(current) || !Number.isFinite(past)) return `${noun}: прошлый срок не посчитался.`
  if (past <= 0 && current <= 0) return `${noun}: и сейчас, и в прошлый срок было 0.`
  if (past <= 0) return `${noun}: в прошлый срок было 0, сейчас ${fmt(current)}.`
  const pct = Math.round(((current - past) / past) * 100)
  if (pct === 0) return `${noun}: столько же, сколько в прошлый срок.`
  return `${noun}: на ${Math.abs(pct)}% ${pct > 0 ? 'больше' : 'меньше'}, чем в прошлый срок.`
}

function LensIcon({ id }) {
  const props = {
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.7,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': true,
  }
  if (id === 'days') {
    return (
      <svg {...props}>
        <path d="M5 19V10M12 19V5M19 19v-7" />
      </svg>
    )
  }
  if (id === 'people') {
    return (
      <svg {...props}>
        <circle cx="12" cy="8" r="3.2" />
        <path d="M5 19c0-3.6 2.8-5.8 7-5.8s7 2.2 7 5.8" />
      </svg>
    )
  }
  if (id === 'compare') {
    return (
      <svg {...props}>
        <path d="M7 8h11M15 5l3 3-3 3" />
        <path d="M17 16H6M9 13l-3 3 3 3" />
      </svg>
    )
  }
  return (
    <svg {...props}>
      <rect x="3.5" y="3.5" width="7" height="7" rx="1.4" />
      <rect x="13.5" y="3.5" width="7" height="7" rx="1.4" />
      <rect x="3.5" y="13.5" width="7" height="7" rx="1.4" />
      <rect x="13.5" y="13.5" width="7" height="7" rx="1.4" />
    </svg>
  )
}

function DeltaNote({ now, before, suffix }) {
  if (before == null || now == null) return null
  const past = Number(before)
  const current = Number(now)
  if (!Number.isFinite(past) || !Number.isFinite(current)) return null
  if (past <= 0) {
    return <em className="act-delta">{current > 0 ? 'в прошлый срок было 0' : 'как в прошлый срок'}</em>
  }
  const pct = Math.round(((current - past) / past) * 100)
  const tone = pct > 0 ? 'is-up' : pct < 0 ? 'is-down' : 'is-flat'
  const sign = pct > 0 ? '+' : ''
  return <em className={`act-delta ${tone}`}>{sign}{pct}% {suffix}</em>
}

function DayBars({ points = [], selected = '', onPick, peakDate = '' }) {
  const max = Math.max(...points.map((p) => Number(p.value) || 0), 1)
  return (
    <>
      <div className="act-bars" aria-label="Сообщения по отрезкам">
        {points.map((point) => {
          const value = Number(point.value) || 0
          const on = selected && selected === point.date
          const h = Math.max(6, Math.round((value / max) * 100))
          return (
            <button
              key={point.date}
              type="button"
              className={[on ? 'is-on' : '', point.date === peakDate && value > 0 ? 'is-hot' : ''].filter(Boolean).join(' ')}
              data-level={levelOf(value, max)}
              title={`${point.label}: ${fmt(value)} сообщений`}
              aria-label={`${point.label}: ${fmt(value)} сообщений`}
              aria-pressed={Boolean(selected && selected === point.date)}
              onClick={() => onPick?.(point.date)}
            >
              <i style={{ height: `${h}%` }} />
            </button>
          )
        })}
      </div>
      {points.length > 0 && points.length <= 14 && (
        <div className="grp-peak-days" aria-hidden="true">
          {points.map((point) => {
            const parts = String(point.date || '').split('-')
            const stamp = parts.length >= 3 ? `${Number(parts[2])}.${parts[1]}` : point.label
            return <span key={point.date}>{stamp}</span>
          })}
        </div>
      )}
    </>
  )
}

function LineStage({ points, selected, onPick, grain }) {
  const width = 640
  const height = 220
  const padL = 18
  const padR = 18
  const padT = 18
  const padB = 28
  const maxMessages = Math.max(...points.map((point) => point.messages), 1)
  const innerW = width - padL - padR
  const innerH = height - padT - padB
  const xAt = (index) => (points.length === 1
    ? padL + innerW / 2
    : padL + (index / (points.length - 1)) * innerW)
  const yMessages = (value) => padT + innerH - (value / maxMessages) * innerH
  const messageLine = points.map((point, index) => `${index ? 'L' : 'M'}${xAt(index).toFixed(1)},${yMessages(point.messages).toFixed(1)}`).join(' ')
  const area = `${messageLine} L${xAt(points.length - 1).toFixed(1)},${(padT + innerH).toFixed(1)} L${xAt(0).toFixed(1)},${(padT + innerH).toFixed(1)} Z`
  const [hover, setHover] = useState(-1)
  const selectedIndex = points.findIndex((point) => point.date === selected)
  const tipIndex = hover >= 0 ? hover : selectedIndex
  const tip = tipIndex >= 0 ? points[tipIndex] : null

  function indexFromClient(clientX, target) {
    const rect = target.getBoundingClientRect()
    if (!rect.width || points.length === 1) return 0
    const viewX = ((clientX - rect.left) / rect.width) * width
    const t = (viewX - padL) / innerW
    return Math.max(0, Math.min(points.length - 1, Math.round(t * (points.length - 1))))
  }

  function move(event) {
    setHover(indexFromClient(event.clientX, event.currentTarget))
  }

  function choose(event) {
    const index = indexFromClient(event.clientX, event.currentTarget)
    const point = points[index]
    if (point) onPick?.(point.date)
  }

  function nudge(event) {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
    event.preventDefault()
    const current = selectedIndex >= 0 ? selectedIndex : 0
    const next = event.key === 'ArrowRight'
      ? Math.min(points.length - 1, current + 1)
      : Math.max(0, current - 1)
    onPick?.(points[next].date)
  }

  const ticks = points.length <= 8
    ? points.map((point, index) => ({ point, index }))
    : [0, Math.floor((points.length - 1) / 2), points.length - 1].map((index) => ({ point: points[index], index }))

  return (
    <div className="act-line">
      <div className="act-legend" aria-hidden="true">
        <span><i className="is-msg" /> Сообщения</span>
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="group"
        tabIndex={0}
        aria-label="Сообщения и сколько людей писало. Нажатие открывает этот отрезок."
        onMouseMove={move}
        onMouseLeave={() => setHover(-1)}
        onClick={choose}
        onKeyDown={nudge}
      >
        {[0.25, 0.5, 0.75, 1].map((step) => {
          const y = padT + innerH - innerH * step
          return <line key={step} x1={padL} x2={width - padR} y1={y} y2={y} className="act-grid" />
        })}
        {points.length > 1 && <path d={area} className="act-area" />}
        {points.length > 1 && <path d={messageLine} className="act-stroke is-msg" />}
        {tip && (
          <line x1={xAt(tipIndex)} x2={xAt(tipIndex)} y1={padT} y2={padT + innerH} className="act-guide" />
        )}
        {points.map((point, index) => (
          <circle
            key={point.date}
            cx={xAt(index)}
            cy={yMessages(point.messages)}
            r={point.date === selected ? 5.5 : 3.2}
            className={point.date === selected ? 'act-dot is-on' : 'act-dot'}
          />
        ))}
        {ticks.map(({ point, index }) => {
          const anchor = index === 0 ? 'start' : index === points.length - 1 ? 'end' : 'middle'
          return (
            <text key={point.date} x={xAt(index)} y={height - 8} textAnchor={anchor} className="act-tick">
              {point.short}
            </text>
          )
        })}
      </svg>
      {tip && (
        <p className="act-tip" style={{ left: `${(xAt(tipIndex) / width) * 100}%` }}>
          <b>{tip.label}</b>
          <span>{fmt(tip.messages)} сообщений</span>
          <span>{fmt(tip.writers)} человек</span>
        </p>
      )}
      <p className="act-read">
        {grain === 'month' ? 'Точка — месяц.' : 'Точка — день.'}
        {' '}Нажмите график, и список ниже покажет, кто писал именно тогда.
      </p>
    </div>
  )
}

function ShareRing({ people, total, onLead, onRest }) {
  const lead = Number(people[0]?.messages) || 0
  const next = (Number(people[1]?.messages) || 0) + (Number(people[2]?.messages) || 0)
  const rest = Math.max(Number(total) - lead - next, 0)
  const parts = [
    { key: 'lead', label: people[0]?.name || 'Первый', value: lead, tone: 'is-lead' },
    { key: 'next', label: 'Ещё двое', value: next, tone: 'is-next' },
    { key: 'rest', label: 'Остальные', value: rest, tone: 'is-rest' },
  ].filter((part) => part.value > 0)
  const sum = parts.reduce((acc, part) => acc + part.value, 0)
  const center = sum > 0 && people.length >= 3
    ? Math.round((lead + next) / sum * 100)
    : (sum > 0 ? Math.round(lead / sum * 100) : 0)
  const caption = people.length >= 3 ? 'трое первых' : 'самый активный'
  const radius = 42
  const length = 2 * Math.PI * radius
  let cursor = 0

  if (sum <= 0) {
    return <p className="act-read">Доли нет: за этот срок сообщений не было.</p>
  }

  return (
    <div className="act-ring">
      <div className="act-ring-figure">
        <svg viewBox="0 0 120 120" role="img" aria-label={`${caption}: ${center} процентов сообщений`}>
          <circle cx="60" cy="60" r={radius} className="act-ring-track" />
          {parts.map((part) => {
            const slice = (part.value / sum) * length
            const node = (
              <circle
                key={part.key}
                cx="60"
                cy="60"
                r={radius}
                className={`act-ring-slice ${part.tone}`}
                transform="rotate(-90 60 60)"
                strokeDasharray={`${slice} ${length - slice}`}
                strokeDashoffset={-cursor}
              />
            )
            cursor += slice
            return node
          })}
        </svg>
        <p className="act-ring-core">
          <strong>{center}</strong>
          <span>процентов</span>
          <em>{caption}</em>
        </p>
      </div>
      <ul className="act-ring-legend">
        {parts.map((part) => {
          const share = Math.round((part.value / sum) * 100)
          const openLead = part.key === 'lead' && people[0]
          return (
            <li key={part.key}>
              <button
                type="button"
                onClick={() => (openLead ? onLead?.(people[0], 0) : onRest?.())}
              >
                <i className={part.tone} />
                <span>{part.label}</span>
                <b>{fmt(part.value)} · {share} %</b>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
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
  peopleOnly = false,
}) {
  const [person, setPerson] = useState(null)
  const [period, setPeriod] = useState(seedPeriod || 'month')
  const [slice, setSlice] = useState(seedSlice || '')
  const [lens, setLens] = useState('overview')
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setSlice(seedSlice || '')
    setPeriod(seedPeriod || 'month')
    setReport(null)
    setPerson(null)
    setLens('overview')
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

  function openPerson(personRow, index) {
    const times = repeats.get(Number(personRow.userId)) || 0
    const total = Number(slice ? report?.messages : report?.periodMessages) || 0
    const share = total > 0 ? Math.round((Number(personRow.messages) || 0) / total * 100) : 0
    setPerson({ ...personRow, share, place: index + 1, times })
  }

  function toggleSlice(date) {
    setSlice(slice === date ? '' : date)
  }

  if (!chatId) {
    return <p className="realm-copy">Сначала выберите группу. Тогда здесь будут сообщения этого чата.</p>
  }

  const series = report?.series || []
  const focus = slice || report?.focus || ''
  const grain = report?.grain || (period === 'year' ? 'month' : 'day')
  const unit = grain === 'month' ? 'месяц' : 'день'
  const chartPoints = series.map((point) => ({
    date: point.date,
    label: longLabel(point.date, grain),
    short: grain === 'month'
      ? (MONTHS[(Number(String(point.date).split('-')[1]) || 1) - 1] || '')
      : `${Number(String(point.date).split('-')[2]) || ''}.${String(point.date).split('-')[1] || ''}`,
    messages: Number(point.messages) || 0,
    writers: Number(point.writers) || 0,
    value: Number(point.messages) || 0,
  }))
  const people = report?.people || []
  const spoken = Number(slice ? report?.messages : report?.periodMessages) || 0
  const writerCount = Number(slice ? report?.writers : report?.periodWriters) || 0
  const periodMessages = Number(report?.periodMessages) || 0
  const periodWriters = Number(report?.periodWriters) || 0
  const peak = chartPoints.reduce((best, point) => (point.value > (best?.value || 0) ? point : best), null)
  const quiet = chartPoints.reduce((best, point) => (best == null || point.value < best.value ? point : best), null)
  const perPerson = writerCount > 0 ? Math.round(spoken / writerCount) : null
  const topThree = people.slice(0, 3).reduce((sum, row) => sum + (Number(row.messages) || 0), 0)
  const topShare = spoken > 0 ? Math.round(topThree / spoken * 100) : 0
  const shownPeople = (!peopleOnly && lens === 'overview' && !slice) ? people.slice(0, 5) : people
  const lenses = [
    { id: 'overview', label: 'Обзор' },
    { id: 'days', label: grain === 'month' ? 'Месяцы' : 'Дни' },
    { id: 'people', label: 'Люди' },
    { id: 'compare', label: 'Сравнение' },
  ]
  const dayAverage = chartPoints.length ? periodMessages / chartPoints.length : 0
  const livelier = dayAverage > 0
    ? chartPoints.filter((point) => point.value > dayAverage).sort((a, b) => b.value - a.value)
    : []
  const averageDelta = slice && chartPoints.length > 1 && dayAverage > 0 ? pctChange(spoken, dayAverage) : null

  const sheet = person && (
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
  )

  const peopleList = (
    <div className="act-people-block">
      <div className="act-block-head">
        <h3 className="realm-h">{slice ? `Кто писал в этот ${unit}` : 'Кто пишет'}</h3>
        {lens === 'overview' && people.length > shownPeople.length && (
          <button type="button" className="gate-text" onClick={() => setLens('people')}>
            Все {fmt(writerCount)}
          </button>
        )}
      </div>
      <p className="act-read">Число справа — сообщения. Нажмите имя: сколько человек пишет и были ли наказания.</p>
      {shownPeople.length === 0 && <p className="act-read">За этот срок никто не писал.</p>}
      <ul className="act-people">
        {shownPeople.map((personRow, index) => {
          const total = spoken
          const share = total > 0 ? Math.round((Number(personRow.messages) || 0) / total * 100) : 0
          const place = people.findIndex((row) => row.userId === personRow.userId)
          return (
            <li key={personRow.userId} style={{ animationDelay: `${index * 40}ms` }}>
              <button
                type="button"
                className="act-person"
                aria-label={`${personRow.name}, ${fmt(personRow.messages)} сообщений. Открыть карточку`}
                onClick={() => openPerson(personRow, place >= 0 ? place : index)}
              >
                <em>{place >= 0 ? place + 1 : index + 1}</em>
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
    </div>
  )

  return (
    <section className={`act-board${peopleOnly ? ' is-people' : ''}${loading ? ' is-loading' : ''}`} aria-busy={loading}>
      {error && <p className="realm-alert" role="alert">{error}</p>}
      {loading && !report && <p className="realm-copy">Считаем сообщения…</p>}
      {report && report.available === false && (
        <p className="realm-copy">Счётчик этого чата сейчас не открылся. Повторите позже. Нулей вместо живых цифр здесь нет.</p>
      )}
      {report && report.available !== false && peopleOnly && (
        <>
          <p className="act-read">{slice ? 'Число справа — сообщения за выбранный день.' : 'Число справа — сообщения за выбранный срок.'} Нажмите имя, чтобы открыть карточку.</p>
          {(report.people || []).length === 0 && <p className="act-read">За этот срок никто не писал.</p>}
          <ul className="act-people">
            {(report.people || []).map((personRow, index) => {
              const total = Number(slice ? report.messages : report.periodMessages) || 0
              const share = total > 0 ? Math.round((Number(personRow.messages) || 0) / total * 100) : 0
              return (
                <li key={personRow.userId} style={{ animationDelay: `${index * 40}ms` }}>
                  <button
                    type="button"
                    className="act-person"
                    aria-label={`${personRow.name}, ${fmt(personRow.messages)} сообщений. Открыть карточку`}
                    onClick={() => openPerson(personRow, index)}
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
        </>
      )}
      {report && report.available !== false && !peopleOnly && (
        <div className="act-desk">
          <div className="act-toolbar">
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
            <div className="act-lenses" role="tablist" aria-label="Что разобрать">
              {lenses.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  role="tab"
                  aria-selected={lens === item.id}
                  className={lens === item.id ? 'is-on' : ''}
                  onClick={() => setLens(item.id)}
                >
                  <LensIcon id={item.id} />
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div className="act-kpis">
            <button type="button" className="act-kpi" onClick={() => setLens('days')}>
              <span>{slice ? `Сообщения за этот ${unit}` : 'Сообщения'}</span>
              <strong>{fmt(spoken)}</strong>
              {slice ? (
                averageDelta == null
                  ? <em className="act-delta">открыть {grain === 'month' ? 'месяцы' : 'дни'}</em>
                  : <em className={`act-delta ${averageDelta > 0 ? 'is-up' : averageDelta < 0 ? 'is-down' : 'is-flat'}`}>{averageDelta > 0 ? '+' : ''}{averageDelta}% к среднему {unit === 'месяц' ? 'месяцу' : 'дню'}</em>
              ) : (
                <DeltaNote now={report.periodMessages} before={report.previousMessages} suffix="к прошлому сроку" />
              )}
            </button>
            <button type="button" className="act-kpi" onClick={() => setLens('people')}>
              <span>{slice ? `Писали в этот ${unit}` : 'Писали'}</span>
              <strong>{fmt(writerCount)}</strong>
              {slice ? (
                <em className="act-delta">открыть людей</em>
              ) : report.previousWriters == null ? (
                <em className="act-delta">открыть список</em>
              ) : (
                <DeltaNote now={report.periodWriters} before={report.previousWriters} suffix="к прошлому сроку" />
              )}
            </button>
            <button type="button" className="act-kpi" onClick={() => setLens('compare')}>
              <span>На человека</span>
              <strong>{perPerson == null ? '—' : fmt(perPerson)}</strong>
              <em className="act-delta">сообщений на одного писавшего</em>
            </button>
            <button type="button" className="act-kpi" onClick={() => setLens('people')}>
              <span>Трое первых</span>
              <strong>{spoken > 0 ? `${topShare} %` : '—'}</strong>
              <em className="act-delta">{people.length >= 3 ? 'доля сообщений' : 'пишущих меньше трёх'}</em>
            </button>
          </div>

          {slice && (
            <button type="button" className="act-clear" onClick={() => setSlice('')}>
              Снова весь срок · сейчас {longLabel(focus, grain)}
            </button>
          )}

          {lens === 'overview' && (
            <div className="act-split">
              <div className="act-stage">
                {chartPoints.length === 0 ? (
                  <p className="act-read">За этот срок ряда нет.</p>
                ) : (
                  <LineStage points={chartPoints} selected={slice} onPick={toggleSlice} grain={grain} />
                )}
              </div>
              <div className="act-stage">
                <h3 className="realm-h">На ком держится чат</h3>
                <ShareRing
                  people={people}
                  total={spoken}
                  onLead={(row) => openPerson(row, 0)}
                  onRest={() => setLens('people')}
                />
              </div>
            </div>
          )}

          {lens === 'days' && (
            <div className="act-stage">
              <div className="act-day-picks">
                {peak?.value > 0 && (
                  <button type="button" className={slice === peak.date ? 'is-on' : ''} onClick={() => toggleSlice(peak.date)}>
                    <span>Самый живой {unit}</span>
                    <strong>{peak.label}</strong>
                    <em>{fmt(peak.value)} сообщений</em>
                  </button>
                )}
                {quiet && peak && quiet.date !== peak.date && quiet.value < peak.value && (
                  <button type="button" className={slice === quiet.date ? 'is-on' : ''} onClick={() => toggleSlice(quiet.date)}>
                    <span>Самый тихий {unit}</span>
                    <strong>{quiet.label}</strong>
                    <em>{fmt(quiet.value)} сообщений</em>
                  </button>
                )}
              </div>
              {chartPoints.length === 0 ? (
                <p className="act-read">За этот срок ряда нет.</p>
              ) : (
                <DayBars
                  points={chartPoints}
                  selected={slice}
                  peakDate={peak?.date || ''}
                  onPick={toggleSlice}
                />
              )}
              <p className="act-read">Нажмите столбик — ниже будет, кто писал в этот {unit}. Повторное нажатие возвращает весь срок.</p>
            </div>
          )}

          {lens === 'compare' && (
            <div className="act-stage act-compare">
              <p className="act-read">{compareSentence(periodMessages, report.previousMessages, 'Сообщения')}</p>
              {report.previousWriters != null && (
                <p className="act-read">{compareSentence(periodWriters, report.previousWriters, 'Люди')}</p>
              )}
              <table className="act-vs">
                <caption>Весь выбранный срок и такой же прошлый. Один день сюда не подмешивается.</caption>
                <thead>
                  <tr>
                    <th scope="col">Показатель</th>
                    <th scope="col">Этот срок</th>
                    <th scope="col">Прошлый</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <th scope="row">Сообщения</th>
                    <td>{fmt(periodMessages)}</td>
                    <td>{fmt(report.previousMessages)}</td>
                  </tr>
                  <tr>
                    <th scope="row">Писали</th>
                    <td>{fmt(periodWriters)}</td>
                    <td>{report.previousWriters == null ? '—' : fmt(report.previousWriters)}</td>
                  </tr>
                  <tr>
                    <th scope="row">На человека</th>
                    <td>{periodWriters > 0 ? fmt(Math.round(periodMessages / periodWriters)) : '—'}</td>
                    <td>{Number(report.previousWriters) > 0 ? fmt(Math.round(Number(report.previousMessages) / Number(report.previousWriters))) : '—'}</td>
                  </tr>
                </tbody>
              </table>
              {livelier.length > 0 && (
                <>
                  <h3 className="realm-h">Живее прошлого срока</h3>
                  <p className="act-read">Эти {grain === 'month' ? 'месяцы' : 'дни'} написали больше, чем средний {unit} прошлого срока. Нажмите — откроется, кто писал.</p>
                  <div className="act-chips">
                    {livelier.map((point) => (
                      <button
                        key={point.date}
                        type="button"
                        className={slice === point.date ? 'is-on' : ''}
                        onClick={() => { setLens('days'); toggleSlice(point.date) }}
                      >
                        {point.label}
                        <b>{fmt(point.value)}</b>
                      </button>
                    ))}
                  </div>
                </>
              )}
              {Number(report.previousMessages) === 0 && (
                <p className="act-read">Прошлый срок был пустым, поэтому живые дни с ним не сравниваются.</p>
              )}
            </div>
          )}

          {(lens === 'overview' || lens === 'people' || (lens === 'days' && slice)) && peopleList}
        </div>
      )}
      {sheet}
    </section>
  )
}
