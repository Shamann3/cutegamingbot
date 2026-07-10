import { useCallback, useEffect, useState } from 'react'
import MaintenanceToggle from '../../components/MaintenanceToggle'
import OnlineAnalyticsShelf from '../../components/OnlineAnalyticsShelf'
import PulseHero from '../../components/PulseHero'
import StatShelfCard from '../../components/StatShelfCard'
import {
  fetchDashboardServer,
  fetchDashboardStats,
  fetchOnlineSummary,
} from '../../lib/adminClient'

export default function DashboardSection() {
  const [stats, setStats] = useState(null)
  const [server, setServer] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

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

  const refreshOnline = useCallback(async () => {
    try {
      const online = await fetchOnlineSummary()
      setStats((prev) => (prev ? { ...prev, ...online } : online))
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    loadDashboard()
  }, [loadDashboard])

  useEffect(() => {
    const id = window.setInterval(refreshOnline, 5000)
    return () => window.clearInterval(id)
  }, [refreshOnline])

  const apiOk = server?.ok && !error

  return (
    <>
      <PulseHero
        onlineNow={stats?.onlineNow}
        todayPeak={stats?.todayPeak}
        windowSeconds={stats?.windowSeconds}
        loading={loading}
      />

      <StatShelfCard
        label="Игроки"
        value={stats?.players}
        hint="В базе"
        loading={loading}
        area="players"
        quiet
      />

      <article className="panel-shelf panel-shelf-server panel-shelf-quiet">
        <p className="panel-shelf-label">Сервер</p>
        <p className="panel-server-title">
          {loading && 'Проверка…'}
          {!loading && apiOk && 'API подключён'}
          {!loading && !apiOk && 'Проблема с API'}
        </p>

        <ul className="panel-server-list">
          <li className={server?.adminBotConfigured ? 'panel-server-ok' : 'panel-server-warn'}>
            Admin-бот {server?.adminBotConfigured ? 'OK' : 'не настроен'}
          </li>
          <li className={server?.jwtConfigured ? 'panel-server-ok' : 'panel-server-warn'}>
            JWT {server?.jwtConfigured ? 'OK' : 'не настроен'}
          </li>
          <li className={server?.maintenance ? 'panel-server-warn' : 'panel-server-ok'}>
            Maintenance {server?.maintenance ? 'включён' : 'выключен'}
          </li>
          {!loading && stats && (
            <>
              <li className="panel-server-ok">Биржа: {stats.marketListings} лотов</li>
              <li className="panel-server-ok">Админов: {stats.adminAccounts}</li>
            </>
          )}
        </ul>

        {error && <p className="panel-shelf-error">{error}</p>}
      </article>

      <article className="panel-shelf panel-shelf-maintenance panel-shelf-quiet">
        {!loading && server && (
          <MaintenanceToggle
            initialEnabled={server.maintenance}
            onChange={(enabled) => setServer((prev) => ({ ...prev, maintenance: enabled }))}
          />
        )}
        {loading && (
          <div className="panel-maintenance">
            <p className="panel-shelf-label">Техработы</p>
            <p className="panel-shelf-muted">Загрузка…</p>
          </div>
        )}
      </article>

      <OnlineAnalyticsShelf />
    </>
  )
}
