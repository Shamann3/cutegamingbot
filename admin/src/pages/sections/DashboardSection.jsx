import { useCallback, useEffect, useRef, useState } from 'react'
import CountUp from '../../components/CountUp'
import {
  fetchDashboardLive,
  fetchDashboardStats,
} from '../../lib/adminClient'
import { useIsPhone } from '../../lib/useIsDesktop'

const PERIODS = [
  { id: 'day', label: 'День', now: 'сегодня', prev: 'вчера' },
  { id: 'week', label: 'Неделя', now: 'эта неделя', prev: 'прошлая неделя' },
  { id: 'month', label: 'Месяц', now: 'этот месяц', prev: 'прошлый месяц' },
  { id: 'year', label: 'Год', now: 'этот год', prev: 'прошлый год' },
]

const LIVE_MS = 1000

function fmt(n) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  return new Intl.NumberFormat('ru-RU').format(Number(n))
}

function toneClass(current, previous) {
  const a = Number(current)
  const b = Number(previous)
  if (!Number.isFinite(a) || !Number.isFinite(b)) return ''
  if (a > b) return 'is-good'
  if (a < b) return 'is-bad'
  return ''
}

function UsageCard({ title, pair, meta, loading }) {
  const current = pair?.current
  const previous = pair?.previous
  return (
    <button type="button" className={`dash-usage-card ${toneClass(current, previous)}`} disabled>
      <span className="dash-usage-label">{title}</span>
      <strong className="dash-usage-value">{loading ? '…' : fmt(current)}</strong>
      <span className="dash-usage-hint">
        {meta.now}
        {previous != null && !loading ? ` · ${meta.prev}: ${fmt(previous)}` : ''}
      </span>
    </button>
  )
}

/** Главная сотрудника: realtime-статистика проекта. */
export default function DashboardSection() {
  const phone = useIsPhone()
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [period, setPeriod] = useState('day')
  const [liveTick, setLiveTick] = useState(0)
  const [liveOk, setLiveOk] = useState(true)
  const inFlight = useRef(false)
  const failStreak = useRef(0)

  const applyPayload = useCallback((data) => {
    if (!data || typeof data !== 'object') return
    setStats((prev) => {
      const nextUsage = data.usage && typeof data.usage === 'object'
        ? {
            ...(prev?.usage || {}),
            ...data.usage,
            botEvents: data.usage.botEvents || prev?.usage?.botEvents,
            newUsers: data.usage.newUsers || prev?.usage?.newUsers,
            officialMessages: data.usage.officialMessages || prev?.usage?.officialMessages,
          }
        : (prev?.usage || {})
      return {
        ...(prev || {}),
        ...data,
        usage: nextUsage,
      }
    })
    setLiveTick((n) => n + 1)
  }, [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setError('')
      try {
        const data = await fetchDashboardStats()
        if (!cancelled) {
          applyPayload(data)
          setLiveOk(true)
        }
      } catch (err) {
        if (!cancelled) setError(err.message || 'Не удалось загрузить панель')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [applyPayload])

  useEffect(() => {
    let cancelled = false
    let timer = 0

    const tick = async () => {
      if (cancelled) return
      if (document.hidden) {
        timer = window.setTimeout(tick, LIVE_MS)
        return
      }
      if (inFlight.current) {
        timer = window.setTimeout(tick, LIVE_MS)
        return
      }
      inFlight.current = true
      try {
        const data = await fetchDashboardLive()
        if (!cancelled) {
          applyPayload(data)
          failStreak.current = 0
          setLiveOk(true)
          setError('')
        }
      } catch (err) {
        failStreak.current += 1
        if (!cancelled && failStreak.current >= 3) {
          setLiveOk(false)
          // Fallback: полный stats, чтобы цифры не зависали на нулях
          try {
            const data = await fetchDashboardStats()
            if (!cancelled) applyPayload(data)
          } catch (statsErr) {
            if (!cancelled) {
              setError(statsErr.message || err.message || 'Статистика недоступна')
            }
          }
        }
      } finally {
        inFlight.current = false
        if (!cancelled) timer = window.setTimeout(tick, LIVE_MS)
      }
    }

    timer = window.setTimeout(tick, 200)
    const onVis = () => {
      if (!document.hidden && !inFlight.current) {
        fetchDashboardLive().then((data) => {
          applyPayload(data)
          setLiveOk(true)
          failStreak.current = 0
        }).catch(() => {})
      }
    }
    document.addEventListener('visibilitychange', onVis)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
      document.removeEventListener('visibilitychange', onVis)
    }
  }, [applyPayload])

  const usage = stats?.usage || {}
  const meta = PERIODS.find((item) => item.id === period) || PERIODS[0]
  const botPair = usage.botEvents?.[period] || { current: 0, previous: 0 }
  const botNow = Number(botPair.current ?? 0)
  const botPrev = Number(botPair.previous ?? 0)

  return (
    <section className={`grp-page nika-page users-page panel-users dash-home dash-cyber${phone ? ' is-phone' : ' is-desktop'}`}>
      <article className="panel-shelf panel-shelf-page panel-users-search dash-home-head dash-cyber-head">
        <p className="panel-shelf-label">Обзор проекта</p>
        <h2 className="panel-page-title">Панель сотрудников CuteGamingBot</h2>
        <p className="panel-page-lead">
          Вызовы команд бота, новые пользователи и сообщения в официальных группах — обновление каждую секунду.
        </p>
        {error && <p className="panel-shelf-error">{error}</p>}
        {!liveOk && !error && (
          <p className="panel-shelf-error">Live-канал нестабилен — читаем полный снимок.</p>
        )}

        <div className="dash-period e-seg" role="tablist" aria-label="Период">
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
      </article>

      <div className="dash-bot-hero" aria-live="polite" data-live={liveTick}>
        <div className="dash-bot-hero-top">
          <span className="dash-bot-hero-kicker">Вызовы бота · все группы</span>
          <span className="dash-bot-hero-live" title="Обновление каждую секунду">
            <span className="dash-bot-hero-live-dot" aria-hidden="true" />
            {liveOk ? '1с' : '…'}
          </span>
        </div>
        <strong className="dash-bot-hero-value">
          {loading ? '…' : <CountUp key={`bot-${period}-${botNow}`} value={botNow} duration={400} />}
        </strong>
        <span className="dash-bot-hero-sub">
          {meta.now}
          {!loading ? ` · ${meta.prev}: ${fmt(botPrev)}` : ''}
        </span>
      </div>

      <div className="panel-shelf panel-users-card dash-usage-stage dash-cyber-stage">
        <div className="dash-usage-grid">
          <UsageCard
            title="Сообщения в официальных группах"
            pair={usage.officialMessages?.[period]}
            meta={meta}
            loading={loading}
          />
          <UsageCard
            title="Новые пользователи"
            pair={usage.newUsers?.[period]}
            meta={meta}
            loading={loading}
          />
          <UsageCard
            title="Вызовы бота"
            pair={usage.botEvents?.[period]}
            meta={meta}
            loading={loading}
          />
        </div>
      </div>

      <article className="panel-shelf panel-shelf-stat panel-shelf-players panel-shelf-quiet dash-db-line">
        <p className="dash-db-line-text">
          {loading
            ? 'В базе данных … пользователей'
            : `В базе данных ${fmt(stats?.players)} пользователей`}
        </p>
      </article>
    </section>
  )
}
