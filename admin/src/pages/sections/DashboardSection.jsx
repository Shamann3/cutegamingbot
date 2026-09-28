import { useCallback, useEffect, useRef, useState } from 'react'
import CountUp from '../../components/CountUp'
import {
  fetchDashboardLive,
  fetchDashboardStats,
} from '../../lib/adminClient'
import { useIsPhone } from '../../lib/useIsDesktop'
import { awaitDashboardStats, readDashboardSnapshot } from '../../lib/dashboardPrefetch'
import { fmt, fmtCompact } from '../../lib/numberFormat'

const PERIODS = [
  { id: 'day', label: 'День', now: 'сегодня', prev: 'вчера' },
  { id: 'week', label: 'Неделя', now: 'эта неделя', prev: 'прошлая неделя' },
  { id: 'month', label: 'Месяц', now: 'этот месяц', prev: 'прошлый месяц' },
  { id: 'year', label: 'Год', now: 'этот год', prev: 'прошлый год' },
]

const LIVE_MS = 1000

function toneClass(current, previous) {
  const a = Number(current)
  const b = Number(previous)
  if (!Number.isFinite(a) || !Number.isFinite(b)) return ''
  if (a > b) return 'is-good'
  if (a < b) return 'is-bad'
  return ''
}

function CollectingCopy() {
  return (
    <span className="dash-collecting">
      <span className="dash-collecting-main">Идёт сбор данных</span>
      <span className="dash-collecting-wait">пожалуйста подождите</span>
    </span>
  )
}

function UsageCard({ title, pair, meta, loading, suffix, period, split }) {
  const current = Number(pair?.current ?? 0)
  const previous = pair?.previous
  return (
    <div
      className={`dash-usage-card${loading ? ' is-collecting' : ''}${split ? ' has-split' : ''} ${loading ? '' : toneClass(current, previous)}`}
    >
      <span className="dash-usage-label">{title}</span>
      {loading ? (
        <CollectingCopy />
      ) : (
        <>
          <strong className="dash-usage-value">
            <CountUp key={`${title}-${period}`} value={current} duration={400} />
            {suffix ? <span className="dash-usage-unit">{suffix}</span> : null}
          </strong>
          <span className="dash-usage-hint">
            {meta.now}
            {previous != null ? ` · ${meta.prev}: ${fmtCompact(previous)}` : ''}
          </span>
          {split && (
            <div className="dash-usage-split">
              <span className="dash-usage-split-item is-lost">
                <span className="dash-usage-split-key">проиграно</span>
                <span className="dash-usage-split-val">{fmtCompact(split.lost)}</span>
              </span>
              <span className="dash-usage-split-item is-won">
                <span className="dash-usage-split-key">выиграно</span>
                <span className="dash-usage-split-val">{fmtCompact(split.won)}</span>
              </span>
            </div>
          )}
        </>
      )}
    </div>
  )
}

/** Главная сотрудника: realtime-статистика проекта. */
export default function DashboardSection() {
  const phone = useIsPhone()
  const primed = readDashboardSnapshot()
  const [stats, setStats] = useState(primed)
  const [loading, setLoading] = useState(!primed)
  const [period, setPeriod] = useState('day')
  const [liveTick, setLiveTick] = useState(0)
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
            allMessages: data.usage.allMessages || prev?.usage?.allMessages,
            officialMessages: data.usage.officialMessages || prev?.usage?.officialMessages,
            gameWager: data.usage.gameWager || prev?.usage?.gameWager,
          }
        : (prev?.usage || {})
      return {
        ...(prev || {}),
        ...data,
        usage: nextUsage,
      }
    })
    setLoading(false)
    setLiveTick((n) => n + 1)
  }, [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      // Сначала — то, что прогрели на экране загрузки. Если данные есть,
      // дальше их ведёт 1 Гц-поллинг, отдельный запрос не нужен.
      const warmed = await awaitDashboardStats()
      if (cancelled) return
      if (warmed) {
        applyPayload(warmed)
        return
      }
      try {
        const data = await fetchDashboardLive()
        if (!cancelled) applyPayload(data)
        return
      } catch {
        // Главный экран без ошибок — пробуем полный снимок.
      }
      try {
        const data = await fetchDashboardStats()
        if (!cancelled) applyPayload(data)
      } catch {
        // Остаёмся в состоянии сбора данных.
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
        }
      } catch {
        failStreak.current += 1
        if (!cancelled && failStreak.current >= 3) {
          try {
            const data = await fetchDashboardStats()
            if (!cancelled) applyPayload(data)
          } catch {
            // тихо
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
        fetchDashboardLive().then(applyPayload).catch(() => {})
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
  const wagerPair = usage.gameWager?.[period] || { current: 0, previous: 0, lost: 0, won: 0 }
  const botNow = Number(botPair.current ?? 0)
  const botPrev = Number(botPair.previous ?? 0)
  const collecting = loading || !stats

  return (
    <section className={`grp-page nika-page users-page panel-users dash-home dash-cyber${phone ? ' is-phone' : ' is-desktop'}`}>
      <article className="panel-shelf panel-shelf-page panel-users-search dash-home-head dash-cyber-head">
        <p className="panel-shelf-label">Обзор проекта</p>
        <h2 className="panel-page-title">Панель сотрудников CuteGamingBot</h2>
        <p className="panel-page-lead">
          Вызовы бота, сообщения в группах и оборот кут в играх — обновление каждую секунду.
        </p>

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

      <div className={`dash-bot-hero${collecting ? ' is-collecting' : ''}`} aria-live="polite" data-live={liveTick}>
        <div className="dash-bot-hero-top">
          <span className="dash-bot-hero-kicker">Вызовы бота · все группы</span>
          {!collecting && (
            <span className="dash-bot-hero-live" title="Обновление каждую секунду">
              <span className="dash-bot-hero-live-dot" aria-hidden="true" />
              1с
            </span>
          )}
        </div>
        {collecting ? (
          <CollectingCopy />
        ) : (
          <>
            <strong className="dash-bot-hero-value">
              <CountUp key={`bot-${period}`} value={botNow} duration={400} />
            </strong>
            <span className="dash-bot-hero-sub">
              {meta.now}
              {` · ${meta.prev}: ${fmt(botPrev)}`}
            </span>
          </>
        )}
      </div>

      <div className="panel-shelf panel-users-card dash-usage-stage dash-cyber-stage" data-live={liveTick}>
        {!collecting && (
          <div className="dash-usage-livebar">
            <span className="dash-bot-hero-live" title="Обновление каждую секунду">
              <span className="dash-bot-hero-live-dot" aria-hidden="true" />
              1с
            </span>
          </div>
        )}
        <div className="dash-usage-grid">
          <UsageCard
            title="Сообщения во всех группах с ботом"
            pair={usage.allMessages?.[period]}
            meta={meta}
            loading={collecting}
            period={period}
          />
          <UsageCard
            title="Оборот кут в системе"
            pair={wagerPair}
            meta={meta}
            loading={collecting}
            period={period}
            suffix=" кут"
            split={{ lost: wagerPair.lost ?? 0, won: wagerPair.won ?? 0 }}
          />
          <UsageCard
            title="Сообщения во всех официальных группах проекта"
            pair={usage.officialMessages?.[period]}
            meta={meta}
            loading={collecting}
            period={period}
          />
        </div>
      </div>

      <article className="panel-shelf panel-shelf-stat panel-shelf-players panel-shelf-quiet dash-db-line">
        {collecting ? (
          <div className="dash-db-line-text">
            <CollectingCopy />
          </div>
        ) : (
          <p className="dash-db-line-text">
            {`В базе данных ${fmt(stats?.players)} пользователей`}
          </p>
        )}
      </article>
    </section>
  )
}
