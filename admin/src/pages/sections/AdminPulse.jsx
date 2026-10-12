import { useEffect, useState } from 'react'
import { fetchAdminPulse } from '../../lib/adminClient'

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

export default function AdminPulse({ chatId, onOpenUser = null }) {
  const [period, setPeriod] = useState('month')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [applied, setApplied] = useState({ start: '', end: '' })
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

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
        <p className="realm-copy">Сообщения администраторов этой группы. Сотрудники проекта сюда не входят.</p>
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
            <article className="adm-pulse-hero is-live">
              <span>Самый живой</span>
              {report.busiest ? (
                <>
                  <strong>{report.busiest.name}</strong>
                  <em>{fmt(report.busiest.messages)} · {report.busiest.position}</em>
                </>
              ) : (
                <strong>Никто не писал</strong>
              )}
            </article>
            <article className="adm-pulse-hero is-quiet">
              <span>Самый тихий</span>
              {report.quietest ? (
                <>
                  <strong>{report.quietest.name}</strong>
                  <em>{fmt(report.quietest.messages)} · {report.quietest.position}</em>
                </>
              ) : (
                <strong>{report.total > 0 ? 'Активность ровная' : 'Все молчат'}</strong>
              )}
            </article>
          </div>
          <p className="adm-pulse-sum">
            {fmt(report.total)} сообщений {spanLabel(report)}
          </p>
          <ol className="adm-pulse-list">
            {people.map((person, index) => (
              <li key={person.userId} style={{ animationDelay: `${Math.min(index, 8) * 40}ms` }}>
                <b>{index + 1}</b>
                {onOpenUser ? (
                  <button type="button" className="e-user-link" onClick={() => onOpenUser(person.userId)}>
                    {person.name}
                  </button>
                ) : (
                  <strong>{person.name}</strong>
                )}
                <span>{person.position}{person.last ? ` · ${person.last}` : ''}</span>
                <i aria-hidden="true"><em style={{ width: `${Math.max(person.share, person.messages > 0 ? 6 : 0)}%` }} /></i>
                <b className="adm-pulse-count">{fmt(person.messages)}</b>
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
    </section>
  )
}
