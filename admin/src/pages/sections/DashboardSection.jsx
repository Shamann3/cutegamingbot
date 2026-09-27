import { useCallback, useEffect, useState } from 'react'
import StatShelfCard from '../../components/StatShelfCard'
import {
  fetchDashboardServer,
  fetchDashboardStats,
} from '../../lib/adminClient'

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
  const [stats, setStats] = useState(null)
  const [server, setServer] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [period, setPeriod] = useState('day')

  const loadDashboard = useCallback(async () => {
    setError('')
    try {
      const [statsData, serverData] = await Promise.all([
        fetchDashboardStats(),
        fetchDashboardServer(),
      ])
      setStats(statsData)
      setServer(serverData)
    } catch (err) {
      setError(err.message || 'Не удалось загрузить панель')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadDashboard()
  }, [loadDashboard])

  const apiOk = Boolean(server?.ok) && !error
  const usage = stats?.usage || {}
  const meta = PERIODS.find((item) => item.id === period) || PERIODS[0]

  return (
    <div className="dash-home">
      <article className="panel-shelf panel-shelf-page dash-home-head">
        <p className="panel-shelf-label">Обзор проекта</p>
        <h2 className="panel-page-title">Использование Epsilon</h2>
        <p className="panel-page-lead">
          Активные пользователи, вызовы бота и сообщения в официальных группах.
        </p>
        {error && <p className="panel-shelf-error">{error}</p>}
      </article>

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

      <div className="dash-usage-grid">
        <article className="panel-shelf dash-usage-active">
          <p className="panel-shelf-label">Активные за сутки</p>
          <p className="panel-stat-value">{loading ? '…' : fmt(usage.activeUsers)}</p>
          <p className="panel-stat-hint">Заходили в проект за последние 24 часа</p>
        </article>

        <UsageCard
          title="Вызовы бота"
          pair={usage.botEvents?.[period]}
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
          title="Сообщения в официальных группах"
          pair={usage.officialMessages?.[period]}
          meta={meta}
          loading={loading}
        />
      </div>

      <StatShelfCard
        label="Количество пользователей в базе данных"
        value={stats?.players}
        loading={loading}
        area="players"
        quiet
      />

      <article className="panel-shelf panel-shelf-server panel-shelf-quiet">
        <p className="panel-shelf-label">Статус панели</p>
        <p className="panel-server-title">
          {loading && 'Проверка…'}
          {!loading && apiOk && 'Всё в норме'}
          {!loading && !apiOk && 'Есть сбой'}
        </p>
      </article>
    </div>
  )
}
