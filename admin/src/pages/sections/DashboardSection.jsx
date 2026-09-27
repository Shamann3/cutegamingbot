import { useCallback, useEffect, useState } from 'react'
import CountUp from '../../components/CountUp'
import {
  fetchDashboardServer,
  fetchDashboardStats,
} from '../../lib/adminClient'
import { useIsPhone } from '../../lib/useIsDesktop'

const PERIODS = [
  { id: 'day', label: 'День', now: 'сегодня', prev: 'вчера' },
  { id: 'month', label: 'Месяц', now: 'этот месяц', prev: 'прошлый месяц' },
  { id: 'year', label: 'Год', now: 'этот год', prev: 'прошлый год' },
]

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

/** Главная сотрудника: общая статистика проекта, без онлайна фермы. */
export default function DashboardSection() {
  const phone = useIsPhone()
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [period, setPeriod] = useState('day')

  const loadDashboard = useCallback(async () => {
    setError('')
    try {
      const [statsData] = await Promise.all([
        fetchDashboardStats(),
        fetchDashboardServer().catch(() => null),
      ])
      setStats(statsData)
    } catch (err) {
      setError(err.message || 'Не удалось загрузить панель')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadDashboard()
  }, [loadDashboard])

  const usage = stats?.usage || {}
  const meta = PERIODS.find((item) => item.id === period) || PERIODS[0]
  const botTotal = Number(usage.botEventsTotal ?? usage.botEvents?.year?.current ?? 0)

  return (
    <section className={`grp-page nika-page users-page panel-users dash-home dash-cyber${phone ? ' is-phone' : ' is-desktop'}`}>
      <article className="panel-shelf panel-shelf-page panel-users-search dash-home-head dash-cyber-head">
        <p className="panel-shelf-label">Обзор проекта</p>
        <h2 className="panel-page-title">Панель сотрудников CuteGamingBot</h2>
        <p className="panel-page-lead">
          Сообщения в официальных группах, новые пользователи и вызовы бота.
        </p>
        {error && <p className="panel-shelf-error">{error}</p>}

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

      <div className="dash-bot-hero" aria-live="polite">
        <span className="dash-bot-hero-kicker">Вызовы бота · все группы</span>
        <strong className="dash-bot-hero-value">
          {loading ? '…' : <CountUp value={botTotal} />}
        </strong>
        <span className="dash-bot-hero-sub">сумма взаимодействий во всех чатах с ботом</span>
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
