import { useCallback, useEffect, useMemo, useState } from 'react'
import OnlineAnalyticsChart from './OnlineAnalyticsChart'
import { fetchOnlineDay, fetchOnlineRange, fetchOnlineSummary } from '../lib/adminClient'

const MODES = [
  { id: 'day', label: 'День', hint: 'по часам' },
  { id: '7d', label: '7 дней', hint: 'по дням' },
  { id: '30d', label: '30 дней', hint: 'по дням' },
  { id: 'month', label: 'Месяц', hint: 'календарь' },
]

function todayLocalIso() {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function currentMonthIso() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function shiftDay(iso, delta) {
  const d = new Date(`${iso}T12:00:00`)
  d.setDate(d.getDate() + delta)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function monthBounds(monthIso) {
  const [y, m] = monthIso.split('-').map(Number)
  const from = `${y}-${String(m).padStart(2, '0')}-01`
  const lastDay = new Date(y, m, 0).getDate()
  const toRaw = `${y}-${String(m).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`
  const today = todayLocalIso()
  return { from, to: toRaw > today ? today : toRaw }
}

function rangeForMode(mode, anchorDay, anchorMonth) {
  const today = todayLocalIso()
  if (mode === 'day') {
    return { from: anchorDay, to: anchorDay, granularity: 'hour' }
  }
  if (mode === '7d') {
    return { from: shiftDay(today, -6), to: today, granularity: 'day' }
  }
  if (mode === '30d') {
    return { from: shiftDay(today, -29), to: today, granularity: 'day' }
  }
  const { from, to } = monthBounds(anchorMonth)
  return { from, to, granularity: 'day' }
}

function formatDayLabel(iso) {
  const today = todayLocalIso()
  const yesterday = shiftDay(today, -1)
  if (iso === today) return 'Сегодня'
  if (iso === yesterday) return 'Вчера'
  try {
    return new Date(`${iso}T12:00:00`).toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
    })
  } catch {
    return iso
  }
}

function formatMonthLabel(monthIso) {
  try {
    const [y, m] = monthIso.split('-')
    return new Date(Number(y), Number(m) - 1, 1).toLocaleDateString('ru-RU', {
      month: 'long',
      year: 'numeric',
    })
  } catch {
    return monthIso
  }
}

function formatPeakTime(iso, withDate = false) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('ru-RU', withDate
      ? { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }
      : { hour: '2-digit', minute: '2-digit' })
  } catch {
    return '—'
  }
}

function currentHourInTz(timezone) {
  try {
    return Number(
      new Intl.DateTimeFormat('en-US', {
        hour: 'numeric',
        hour12: false,
        timeZone: timezone || 'Europe/Moscow',
      }).format(new Date()),
    )
  } catch {
    return new Date().getHours()
  }
}

function normalizeHourPoints(hours, timezone, isToday) {
  const currentHour = isToday ? currentHourInTz(timezone) : null
  let peakHour = null
  let peakValue = 0
  for (const slot of hours) {
    if (slot.peak >= peakValue) {
      peakValue = slot.peak
      peakHour = slot.hour
    }
  }

  return hours.map((slot) => ({
    id: `h-${slot.hour}`,
    label: `${String(slot.hour).padStart(2, '0')}:00`,
    shortLabel: slot.hour % 3 === 0 ? String(slot.hour).padStart(2, '0') : `${slot.hour}`,
    peak: slot.peak,
    avg: slot.avg,
    peakAt: null,
    peakAtLabel: null,
    isCurrent: currentHour === slot.hour,
    isPeak: peakHour === slot.hour && slot.peak > 0,
  }))
}

function normalizeDayPoints(points, timezone) {
  const today = todayLocalIso()
  let peakDate = null
  let peakValue = 0
  for (const slot of points) {
    if (slot.peak >= peakValue) {
      peakValue = slot.peak
      peakDate = slot.date
    }
  }

  return points.map((slot) => {
    const d = new Date(`${slot.date}T12:00:00`)
    return {
      id: `d-${slot.date}`,
      label: d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', weekday: 'short' }),
      shortLabel: d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }),
      peak: slot.peak,
      avg: slot.avg,
      peakAt: slot.peakAt,
      peakAtLabel: slot.peakAt ? formatPeakTime(slot.peakAt, slot.date !== today) : null,
      isCurrent: slot.date === today,
      isPeak: slot.date === peakDate && slot.peak > 0,
    }
  })
}

function periodTitle(mode, anchorDay, anchorMonth, range) {
  if (mode === 'day') return formatDayLabel(anchorDay)
  if (mode === 'month') return formatMonthLabel(anchorMonth)
  if (mode === '7d') return 'Последние 7 дней'
  return 'Последние 30 дней'
}

export default function OnlineAnalyticsShelf() {
  const [summary, setSummary] = useState(null)
  const [mode, setMode] = useState('day')
  const [anchorDay, setAnchorDay] = useState(todayLocalIso)
  const [anchorMonth, setAnchorMonth] = useState(currentMonthIso)
  const [payload, setPayload] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const range = useMemo(
    () => rangeForMode(mode, anchorDay, anchorMonth),
    [mode, anchorDay, anchorMonth],
  )

  const loadSummary = useCallback(async () => {
    try {
      const data = await fetchOnlineSummary()
      setSummary(data)
    } catch {
      // ignore
    }
  }, [])

  const loadAnalytics = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      if (range.granularity === 'hour') {
        const data = await fetchOnlineDay(range.from)
        setPayload(data)
      } else {
        const data = await fetchOnlineRange(range.from, range.to)
        setPayload(data)
      }
    } catch (err) {
      setError(err.message || 'Не удалось загрузить аналитику')
      setPayload(null)
    } finally {
      setLoading(false)
    }
  }, [range])

  useEffect(() => {
    loadSummary()
    const id = window.setInterval(loadSummary, 5000)
    return () => window.clearInterval(id)
  }, [loadSummary])

  useEffect(() => {
    loadAnalytics()
  }, [loadAnalytics])

  const isToday = mode === 'day' && anchorDay === todayLocalIso()
  const timezone = payload?.timezone || 'Europe/Moscow'

  const chartPoints = useMemo(() => {
    if (!payload) return []
    if (range.granularity === 'hour') {
      return normalizeHourPoints(payload.hours || [], timezone, isToday)
    }
    return normalizeDayPoints(payload.points || [], timezone)
  }, [payload, range.granularity, timezone, isToday])

  const periodPeak = payload?.peak ?? 0
  const periodAvg = payload?.avg ?? 0
  const periodPeakAt = payload?.peakAt
  const canGoForwardDay = anchorDay < todayLocalIso()
  const canGoForwardMonth = anchorMonth < currentMonthIso()

  const shiftPeriod = (delta) => {
    if (mode === 'day') {
      setAnchorDay((d) => shiftDay(d, delta))
      return
    }
    if (mode === 'month') {
      const [y, m] = anchorMonth.split('-').map(Number)
      const next = new Date(y, m - 1 + delta, 1)
      const nextIso = `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, '0')}`
      if (nextIso <= currentMonthIso()) setAnchorMonth(nextIso)
    }
  }

  return (
    <article className="panel-shelf panel-shelf-online">
      <div className="panel-online-head">
        <div className="panel-online-title-block">
          <div className="panel-online-title-row">
            <p className="panel-shelf-label">Аналитика онлайна</p>
            {summary && (
              <span className="panel-online-live-badge">
                <span className="panel-live-dot" aria-hidden="true" />
                {summary.onlineNow?.toLocaleString('ru-RU')} online
              </span>
            )}
          </div>
          <p className="panel-online-sub">
            Heartbeat WebApp · окно {summary?.windowSeconds ?? 30} сек · {timezone}
          </p>
        </div>
      </div>

      <div className="online-analytics-modes">
        {MODES.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`online-analytics-mode${mode === item.id ? ' online-analytics-mode-active' : ''}`}
            onClick={() => setMode(item.id)}
          >
            <span className="online-analytics-mode-label">{item.label}</span>
            <span className="online-analytics-mode-hint">{item.hint}</span>
          </button>
        ))}
      </div>

      {(mode === 'day' || mode === 'month') && (
        <div className="panel-online-nav online-analytics-period-nav">
          <button
            type="button"
            className="panel-online-nav-btn"
            onClick={() => shiftPeriod(-1)}
            aria-label="Предыдущий период"
          >
            ‹
          </button>

          {mode === 'day' && (
            <>
              <button
                type="button"
                className={`panel-online-nav-chip${isToday ? ' panel-online-nav-chip-active' : ''}`}
                onClick={() => setAnchorDay(todayLocalIso())}
              >
                Сегодня
              </button>
              <button
                type="button"
                className={`panel-online-nav-chip${anchorDay === shiftDay(todayLocalIso(), -1) ? ' panel-online-nav-chip-active' : ''}`}
                onClick={() => setAnchorDay(shiftDay(todayLocalIso(), -1))}
              >
                Вчера
              </button>
              <label className="panel-online-date-field">
                <input
                  className="panel-online-date-input"
                  type="date"
                  value={anchorDay}
                  max={todayLocalIso()}
                  onChange={(e) => setAnchorDay(e.target.value)}
                />
              </label>
            </>
          )}

          {mode === 'month' && (
            <label className="panel-online-date-field">
              <input
                className="panel-online-date-input online-analytics-month-input"
                type="month"
                value={anchorMonth}
                max={currentMonthIso()}
                onChange={(e) => setAnchorMonth(e.target.value)}
              />
            </label>
          )}

          <span className="online-analytics-period-title">
            {periodTitle(mode, anchorDay, anchorMonth, range)}
          </span>

          <button
            type="button"
            className="panel-online-nav-btn"
            onClick={() => shiftPeriod(1)}
            disabled={mode === 'day' ? !canGoForwardDay : !canGoForwardMonth}
            aria-label="Следующий период"
          >
            ›
          </button>
        </div>
      )}

      <div className="panel-online-stats">
        <div className="panel-online-stat">
          <span className="panel-online-stat-label">Сейчас</span>
          <strong className="panel-online-stat-value panel-online-stat-value-live">
            {summary?.onlineNow != null ? summary.onlineNow.toLocaleString('ru-RU') : '—'}
          </strong>
          <span className="panel-online-stat-hint">live · каждые 5 сек</span>
        </div>

        <div className="panel-online-stat">
          <span className="panel-online-stat-label">Пик периода</span>
          <strong className="panel-online-stat-value">
            {loading ? '…' : periodPeak.toLocaleString('ru-RU')}
          </strong>
          <span className="panel-online-stat-hint">
            {!loading && periodPeakAt ? formatPeakTime(periodPeakAt, mode !== 'day') : '—'}
          </span>
        </div>

        <div className="panel-online-stat">
          <span className="panel-online-stat-label">Средний онлайн</span>
          <strong className="panel-online-stat-value">
            {loading ? '…' : periodAvg.toLocaleString('ru-RU')}
          </strong>
          <span className="panel-online-stat-hint">
            {range.granularity === 'hour' ? 'по активным часам' : 'по активным дням'}
          </span>
        </div>
      </div>

      {error && <p className="panel-shelf-error panel-online-error">{error}</p>}

      {!loading && payload && !payload.hasData && !error && (
        <div className="panel-online-empty">
          <p className="panel-online-empty-title">Пока нет данных за этот период</p>
          <p className="panel-online-empty-text">
            Снимки онлайна сохраняются каждую минуту. Как только игроки зайдут — график заполнится.
          </p>
        </div>
      )}

      {(loading || (payload?.hasData && chartPoints.length > 0)) && (
        <OnlineAnalyticsChart
          points={chartPoints}
          granularity={range.granularity}
          loading={loading}
        />
      )}
    </article>
  )
}
