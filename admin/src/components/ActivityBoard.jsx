import { useEffect, useState } from 'react'
import { fetchGroupActivity } from '../lib/adminClient'
import { HabitGrid } from './sight/SightCharts'

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

export default function ActivityBoard({ chatId, repeats = new Map(), canPunish = false, onPick }) {
  const [period, setPeriod] = useState('month')
  const [slice, setSlice] = useState('')
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setSlice('')
    setReport(null)
  }, [chatId])

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

  return (
    <section className="act-board">
      <div className="realm-actions" role="tablist" aria-label="Период">
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
          <div className="act-figures">
            <button type="button" className={slice ? '' : 'is-on'} onClick={() => setSlice('')}>
              <strong>{fmt(slice ? report.messages : report.periodMessages)}</strong>
              <span>{slice ? 'сообщений в выбранной точке' : 'сообщений за период'}</span>
            </button>
            <p>
              <strong>{fmt(slice ? report.writers : report.periodWriters)}</strong>
              <span>человек писали</span>
            </p>
          </div>
          <p className="realm-copy">
            {slice
              ? `${longLabel(focus, grain)}. Нажмите клетку ещё раз или «весь период», чтобы вернуть общий счёт.`
              : `Прошлый такой же отрезок: ${fmt(report.previousMessages)} сообщений. Нажмите клетку, чтобы увидеть этот день или месяц.`}
          </p>
          <HabitGrid
            caption={grain === 'month' ? 'Сетка месяцев: светлее — больше сообщений.' : 'Сетка дней: светлее — больше сообщений. Нажмите клетку, чтобы открыть этот день.'}
            selected={slice}
            onPick={(date) => setSlice(slice === date ? '' : date)}
            points={series.map((point) => ({
              date: point.date,
              label: longLabel(point.date, grain),
              value: Number(point.messages) || 0,
            }))}
          />
          <h3 className="realm-h">Кто пишет</h3>
          {(report.people || []).length === 0 && <p className="realm-copy">За этот отрезок список пишущих пуст.</p>}
          <ul className="realm-list">
            {(report.people || []).map((person) => {
              const times = repeats.get(Number(person.userId)) || 0
              return (
                <li key={person.userId}>
                  <div className="realm-row">
                    <strong>{person.name}{times >= 2 ? ` · в архиве ${times}` : ''}</strong>
                    <span>{fmt(person.messages)}</span>
                  </div>
                  {canPunish && (
                    <button type="button" className="realm-text-act" onClick={() => onPick?.(String(person.userId))}>
                      В форму
                    </button>
                  )}
                </li>
              )
            })}
          </ul>
        </>
      )}
    </section>
  )
}
