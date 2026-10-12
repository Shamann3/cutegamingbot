import { useEffect, useState } from 'react'
import FocusWindow from '../../components/FocusWindow'
import { fetchAdminPulse, fetchPersonHistory } from '../../lib/adminClient'
import { watchLevel, watchLine } from '../../lib/shiftDesk'

const PERIODS = [
  { id: 'day', label: 'День' },
  { id: 'week', label: 'Неделя' },
  { id: 'month', label: 'Месяц' },
  { id: 'year', label: 'Год' },
  { id: 'all', label: 'Всё время' },
  { id: 'custom', label: 'Свои даты' },
]

function fmt(value) {
  return new Intl.NumberFormat('ru-RU').format(Number(value) || 0)
}

function spanLabel(report) {
  if (!report || report.period === 'all') return 'за всё время'
  if (report.from && report.to && report.from !== report.to) return `${report.from} — ${report.to}`
  if (report.from) return report.from
  return ''
}

function deedRows(report) {
  if (!report || report.available === false || !Array.isArray(report.counts)) return null
  return report.counts.filter((row) => Number(row.count) > 0)
}

function PulseCard({ person, place, mark, chatId, watch, onClose, onOpenUser }) {
  const [ledger, setLedger] = useState(null)
  const [state, setState] = useState('loading')
  const [fault, setFault] = useState('')
  const handle = person.username ? `@${String(person.username).replace(/^@/, '')}` : ''
  const warned = (watch || []).find((item) => Number(item.userId) === Number(person.userId))

  useEffect(() => {
    let stop = false
    setLedger(null)
    setState('loading')
    setFault('')
    fetchPersonHistory(chatId, person.userId)
      .then((data) => {
        if (stop) return
        setLedger(data)
        setState('ready')
      })
      .catch((err) => {
        if (stop) return
        setFault(err?.message || 'Счётчик наказаний не открылся')
        setState('error')
      })
    return () => { stop = true }
  }, [chatId, person.userId])

  const deeds = deedRows(ledger)

  return (
    <FocusWindow
      title={person.name}
      subtitle={[handle, person.position].filter(Boolean).join(' · ') || `#${person.userId}`}
      onClose={onClose}
      footer={onOpenUser ? (
        <button
          type="button"
          className="sec-btn"
          onClick={() => {
            const id = person.userId
            onClose()
            onOpenUser(id)
          }}
        >
          Наказания этого человека
        </button>
      ) : null}
    >
      <dl className="adm-pulse-facts">
        <div>
          <dt>Место</dt>
          <dd>{mark || `${place} среди администраторов`}</dd>
        </div>
        <div>
          <dt>Сообщения</dt>
          <dd>{fmt(person.messages)}</dd>
        </div>
        <div>
          <dt>Доля</dt>
          <dd>{person.share}% среди администраторов</dd>
        </div>
        <div>
          <dt>Последний раз</dt>
          <dd>{person.last || 'ещё не было'}</dd>
        </div>
      </dl>
      <p className="realm-copy">
        {warned ? watchLine(watchLevel(warned.warns), warned.warns) : 'Активных предупреждений нет.'}
      </p>
      <div className="adm-pulse-deeds" aria-live="polite">
        <h3 className="realm-h">Какие наказания уже были</h3>
        {state === 'loading' && <p className="realm-copy">Считаем наказания…</p>}
        {state === 'error' && <p className="chat-admins-warn">{fault}</p>}
        {state === 'ready' && ledger?.available === false && (
          <p className="realm-copy">Счётчик наказаний не открылся. Нулей вместо записей здесь нет.</p>
        )}
        {state === 'ready' && deeds == null && <p className="realm-copy">Разбивка по видам не пришла.</p>}
        {state === 'ready' && deeds?.length === 0 && <p className="realm-copy">Наказаний ещё не было.</p>}
        {state === 'ready' && deeds?.length > 0 && (
          <ul>
            {deeds.map((row) => (
              <li key={row.action}>
                <span>
                  <strong>{row.label || row.action}</strong>
                  {row.hint ? <em>{row.hint}</em> : null}
                </span>
                <b>{fmt(row.count)}</b>
              </li>
            ))}
          </ul>
        )}
      </div>
    </FocusWindow>
  )
}

export default function AdminPulse({ chatId, onOpenUser = null, watch = [] }) {
  const [period, setPeriod] = useState('month')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [applied, setApplied] = useState({ start: '', end: '' })
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [focus, setFocus] = useState(null)

  useEffect(() => {
    if (!chatId) return undefined
    if (period === 'custom' && (!applied.start || !applied.end)) {
      setLoading(false)
      setReport(null)
      return undefined
    }
    let stop = false
    setLoading(true)
    setError('')
    fetchAdminPulse(chatId, {
      period,
      start: period === 'custom' ? applied.start : '',
      end: period === 'custom' ? applied.end : '',
    })
      .then((data) => { if (!stop) setReport(data) })
      .catch((err) => { if (!stop) setError(err?.message || 'Сводка не открылась') })
      .finally(() => { if (!stop) setLoading(false) })
    return () => { stop = true }
  }, [chatId, period, applied])

  const people = report?.available === false ? [] : (report?.people || [])
  const key = `${period}:${report?.from || ''}:${report?.to || ''}:${report?.total ?? ''}`

  function applyDates(event) {
    event.preventDefault()
    if (!from || !to || to < from) {
      setError('Сначала начало, потом конец')
      return
    }
    setError('')
    setPeriod('custom')
    setApplied({ start: from, end: to })
  }

  return (
    <section className="adm-pulse" aria-busy={loading}>
      <div className="adm-pulse-head">
        <h2 className="realm-h">Кто держит чат</h2>
        <p className="realm-copy">Сообщения администраторов этой группы. Сотрудники проекта сюда не входят. Нажмите карточку или строку — откроется человек: сколько писал, какая доля и какие наказания уже были.</p>
      </div>
      <div className="adm-pulse-periods" role="tablist" aria-label="Срок сводки">
        {PERIODS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={period === item.id}
            className={period === item.id ? 'is-on' : ''}
            onClick={() => {
              setPeriod(item.id)
              if (item.id !== 'custom') setError('')
            }}
          >
            {item.label}
          </button>
        ))}
      </div>
      {period === 'custom' && (
        <form className="adm-pulse-dates" onSubmit={applyDates}>
          <label>
            С
            <input type="date" value={from} max={to || undefined} onChange={(event) => setFrom(event.target.value)} required />
          </label>
          <label>
            По
            <input type="date" value={to} min={from || undefined} onChange={(event) => setTo(event.target.value)} required />
          </label>
          <button type="submit">Показать</button>
        </form>
      )}
      {error && <p className="chat-admins-warn">{error}</p>}
      {loading && !report && <p className="realm-copy">Считаем сообщения администраторов…</p>}
      {report?.available === false && (
        <p className="realm-copy">Счётчик сейчас не открылся. Нулей вместо живых цифр здесь нет.</p>
      )}
      {report?.available !== false && people.length > 0 && (
        <div key={key}>
          <div className="adm-pulse-pair">
            <PulseHero
              tone="is-live"
              label="Самый живой"
              person={report.busiest}
              empty="Никто не писал"
              onOpen={setFocus}
            />
            <PulseHero
              tone="is-quiet"
              label="Самый тихий"
              person={report.quietest}
              empty={report.total > 0 ? 'Активность ровная' : 'Все молчат'}
              onOpen={setFocus}
            />
          </div>
          <p className="adm-pulse-sum">
            {fmt(report.total)} сообщений {spanLabel(report)}
          </p>
          <ol className="adm-pulse-list">
            {people.map((person, index) => (
              <li key={person.userId} style={{ animationDelay: `${Math.min(index, 8) * 40}ms` }}>
                <button
                  type="button"
                  className="adm-pulse-row"
                  aria-label={`${person.name}, ${fmt(person.messages)} сообщений. Открыть карточку`}
                  onClick={() => setFocus(person)}
                >
                  <b>{index + 1}</b>
                  <strong>{person.name}</strong>
                  <span>{person.position}{person.last ? ` · ${person.last}` : ''}</span>
                  <i aria-hidden="true"><em style={{ width: `${Math.max(person.share, person.messages > 0 ? 6 : 0)}%` }} /></i>
                  <b className="adm-pulse-count">{fmt(person.messages)}</b>
                </button>
              </li>
            ))}
          </ol>
        </div>
      )}
      {report?.available !== false && !loading && people.length === 0 && period !== 'custom' && (
        <p className="realm-copy">Администраторов с должностью в этой группе пока нет.</p>
      )}
      {period === 'custom' && !applied.start && !loading && (
        <p className="realm-copy">Выберите начало и конец, затем «Показать».</p>
      )}
      {focus && (
        <PulseCard
          person={focus}
          place={(people.findIndex((row) => row.userId === focus.userId) + 1) || 1}
          mark={
            report?.busiest?.userId === focus.userId
              ? 'Самый живой'
              : report?.quietest?.userId === focus.userId
                ? 'Самый тихий'
                : ''
          }
          chatId={chatId}
          watch={watch}
          onClose={() => setFocus(null)}
          onOpenUser={onOpenUser}
        />
      )}
    </section>
  )
}

function PulseHero({ tone, label, person, empty, onOpen }) {
  const body = person ? (
    <>
      <strong>{person.name}</strong>
      <em>{fmt(person.messages)} · {person.position}</em>
    </>
  ) : (
    <strong>{empty}</strong>
  )
  if (!person) {
    return (
      <article className={`adm-pulse-hero ${tone}`}>
        <span>{label}</span>
        {body}
      </article>
    )
  }
  return (
    <button
      type="button"
      className={`adm-pulse-hero is-person ${tone}`}
      aria-label={`${label}, ${person.name}. Открыть карточку`}
      onClick={() => onOpen(person)}
    >
      <span>{label}</span>
      {body}
    </button>
  )
}
