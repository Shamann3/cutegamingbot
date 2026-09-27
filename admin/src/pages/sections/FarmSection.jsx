import { useCallback, useEffect, useMemo, useState } from 'react'
import AdminActionModal from '../../components/AdminActionModal'
import SeedEconomySettings from '../../components/SeedEconomySettings'
import {
  fetchEconomyOverview,
  fetchFarmOverview,
  fetchFarmUser,
  fetchOnlineSummary,
  globalFarmReset,
  resetFarmUserPlots,
  saveEconomySettings,
  saveFarmSettings,
  searchAdminUsers,
} from '../../lib/adminClient'
import { parseRequiredIntFields } from '../../lib/formNumbers'
import { notifyAdmin } from '../../lib/notify'
import UserLookupPreview from '../../components/UserLookupPreview'
import { IdentityBits } from '../../components/Copyable'
import { filterSectionTabs } from '../../constants/panelAccessTree'

const FARM_TABS = [
  { id: 'plots', label: '🌱 Грядки' },
  { id: 'seed', label: '🌿 Семена' },
]

const GLOBAL_RESET_PASSWORD = 'legehdarg341234123412'

function formatSec(sec) {
  if (sec == null) return '-'
  const m = Math.floor(Number(sec) / 60)
  const s = Number(sec) % 60
  if (m >= 60) {
    const h = Math.floor(m / 60)
    const rm = m % 60
    return rm ? `${h}ч ${rm}м` : `${h}ч`
  }
  return s ? `${m}м ${s}с` : `${m}м`
}

const PLOT_STATUS_LABEL = {
  EMPTY: 'Пусто',
  GROWING: 'Растёт',
  READY: 'Готово',
  WITHERED: 'Засохло',
}

export default function FarmSection({ onOpenUser, isProjectCreator = false, panelTabs = null } = {}) {
  const tabs = filterSectionTabs('farm', FARM_TABS, panelTabs)
  const [tab, setTab] = useState(tabs[0]?.id || 'plots')
  const activeTab = tabs.some((t) => t.id === tab) ? tab : (tabs[0]?.id || 'plots')
  const [overview, setOverview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')

  const [treeGrow, setTreeGrow] = useState('')
  const [tobaccoGrow, setTobaccoGrow] = useState('')
  const [maxPlots, setMaxPlots] = useState('')
  const [plotPriceStep, setPlotPriceStep] = useState('')
  const [clearCost, setClearCost] = useState('')
  const [waterInterval, setWaterInterval] = useState('')
  const [wiltGrace, setWiltGrace] = useState('')
  const [waterCost, setWaterCost] = useState('')

  const [playerQuery, setPlayerQuery] = useState('')
  const [playerResolvedId, setPlayerResolvedId] = useState(null)
  const [playerFarm, setPlayerFarm] = useState(null)
  const [playerLoading, setPlayerLoading] = useState(false)
  const [resetTarget, setResetTarget] = useState(null)
  const [resettingPlot, setResettingPlot] = useState(null)
  const [globalResetOpen, setGlobalResetOpen] = useState(false)
  const [globalResetting, setGlobalResetting] = useState(false)
  const [globalResetPassword, setGlobalResetPassword] = useState('')
  const [farmPeriod, setFarmPeriod] = useState('day')
  const [farmFocus, setFarmFocus] = useState(null)
  const [online, setOnline] = useState(null)

  const applySettings = useCallback((settings) => {
    if (!settings) return
    setTreeGrow(String(settings.treeGrowSeconds ?? ''))
    setTobaccoGrow(String(settings.tobaccoGrowSeconds ?? ''))
    setMaxPlots(String(settings.maxPlots ?? ''))
    setPlotPriceStep(String(settings.plotPriceStep ?? ''))
    setWaterInterval(String(settings.waterIntervalSeconds ?? ''))
    setWiltGrace(String(settings.wiltGraceSeconds ?? ''))
    setWaterCost(String(settings.waterCostPerUse ?? ''))
    if (settings.clearCost != null) {
      setClearCost(String(settings.clearCost))
    }
  }, [])

  const loadOverview = useCallback(async () => {
    setError('')
    try {
      const [data, economy] = await Promise.all([
        fetchFarmOverview(),
        fetchEconomyOverview().catch(() => null),
      ])
      setOverview(data)
      applySettings({
        ...data.settings,
        clearCost: data.settings?.clearCost ?? economy?.settings?.clearCost,
      })
    } catch (err) {
      setError(err.message || 'Не удалось загрузить ферму')
    } finally {
      setLoading(false)
    }
  }, [applySettings])

  useEffect(() => {
    loadOverview()
  }, [loadOverview])

  useEffect(() => {
    let stop = false
    const tick = () => {
      fetchOnlineSummary()
        .then((data) => { if (!stop) setOnline(data) })
        .catch(() => {})
    }
    tick()
    const id = window.setInterval(tick, 8000)
    return () => {
      stop = true
      window.clearInterval(id)
    }
  }, [])

  const handleSaveSettings = async () => {
    setError('')
    setInfo('')
    let farmPayload
    let economyPayload
    try {
      farmPayload = parseRequiredIntFields(
        {
          treeGrowSeconds: treeGrow,
          tobaccoGrowSeconds: tobaccoGrow,
          maxPlots,
          plotPriceStep,
          waterIntervalSeconds: waterInterval,
          wiltGraceSeconds: wiltGrace,
          waterCostPerUse: waterCost,
        },
        {
          treeGrowSeconds: 'Дерево - рост (сек)',
          tobaccoGrowSeconds: 'Табак - рост (сек)',
          maxPlots: 'Макс. грядок',
          plotPriceStep: 'Шаг цены грядки',
          waterIntervalSeconds: 'Интервал полива (сек)',
          wiltGraceSeconds: 'Засуха - grace (сек)',
          waterCostPerUse: 'Вода за полив (шт.)',
        },
      )
      economyPayload = parseRequiredIntFields(
        { clearCost },
        { clearCost: 'Очистка засохшей грядки' },
      )
    } catch (err) {
      const message = err.message || 'Проверьте поля настроек'
      setError(message)
      notifyAdmin(message, { error: true })
      return
    }

    setSaving(true)
    try {
      const [settings] = await Promise.all([
        saveFarmSettings(farmPayload),
        saveEconomySettings(economyPayload),
      ])
      const message = `Сохранено. Макс. грядок: ${settings.maxPlots ?? farmPayload.maxPlots}`
      setInfo(message)
      notifyAdmin(message)
      applySettings({ ...settings, clearCost: economyPayload.clearCost })
      await loadOverview()
    } catch (err) {
      const message = err.message || 'Ошибка сохранения'
      setError(message)
      notifyAdmin(message, { error: true })
    } finally {
      setSaving(false)
    }
  }

  const loadPlayer = async (userId) => {
    setPlayerLoading(true)
    setError('')
    try {
      const farm = await fetchFarmUser(userId)
      setPlayerFarm(farm)
    } catch (err) {
      setError(err.message || 'Игрок не найден')
      setPlayerFarm(null)
    } finally {
      setPlayerLoading(false)
    }
  }

  const handlePlayerSearch = async (e) => {
    e.preventDefault()
    const uid = playerResolvedId || (/^\d+$/.test(playerQuery.trim()) ? Number(playerQuery.trim()) : null)
    if (uid) {
      setPlayerLoading(true)
      setError('')
      try {
        await loadPlayer(Number(uid))
      } catch (err) {
        setError(err.message || 'Ошибка поиска')
      } finally {
        setPlayerLoading(false)
      }
      return
    }
    const q = playerQuery.trim()
    if (!q) return
    setPlayerLoading(true)
    setError('')
    try {
      const data = await searchAdminUsers(q)
      const list = data.results || []
      if (list.length === 1) {
        await loadPlayer(list[0].userId)
      } else if (list.length === 0) {
        setPlayerFarm(null)
        setError('Никого не найдено')
      } else {
        setPlayerFarm(null)
        setError(`Найдено ${list.length} — выберите игрока в превью`)
      }
    } catch (err) {
      setError(err.message || 'Ошибка поиска')
    } finally {
      setPlayerLoading(false)
    }
  }

  const confirmReset = async () => {
    if (!playerFarm?.userId || resetTarget == null) return
    const target = resetTarget
    const plotId = target === 'all' ? null : target
    setResettingPlot(target)
    setResetTarget(null)
    try {
      const result = await resetFarmUserPlots(playerFarm.userId, plotId)
      setPlayerFarm(result.farm)
      setInfo(
        target === 'all'
          ? `Сброшено грядок: ${result.plotsReset}`
          : `Грядка #${target} сброшена`,
      )
      notifyAdmin(
        target === 'all'
          ? `Сброшено грядок: ${result.plotsReset}`
          : `Грядка #${target} сброшена`,
      )
      await loadOverview()
    } catch (err) {
      const message = err.message || 'Не удалось сбросить'
      setError(message)
      notifyAdmin(message, { error: true })
    } finally {
      setResettingPlot(null)
    }
  }

  const confirmGlobalReset = async () => {
    if (globalResetPassword !== GLOBAL_RESET_PASSWORD) {
      const message = 'Неверный пароль'
      setError(message)
      notifyAdmin(message, { error: true })
      return
    }
    setGlobalResetting(true)
    setError('')
    setInfo('')
    try {
      const result = await globalFarmReset()
      setGlobalResetOpen(false)
      setGlobalResetPassword('')
      setInfo(`Глобальный сброс: ${result.plotsReset} грядок очищено`)
      notifyAdmin(`Глобальный сброс: ${result.plotsReset} грядок`)
      if (playerFarm?.userId) await loadPlayer(playerFarm.userId)
      await loadOverview()
    } catch (err) {
      const message = err.message || 'Ошибка глобального сброса'
      setError(message)
      notifyAdmin(message, { error: true })
    } finally {
      setGlobalResetting(false)
    }
  }

  const plotPreview = useMemo(() => {
    const max = Number(maxPlots)
    const step = Number(plotPriceStep)
    if (!Number.isFinite(max) || max < 2 || !Number.isFinite(step) || step < 1) return []
    return Array.from({ length: max - 1 }, (_, index) => {
      const plotId = index + 2
      return { plotId, price: (plotId - 1) * step }
    })
  }, [maxPlots, plotPriceStep])

  const stats = overview?.stats
  const crops = overview?.crops || []
  const env = overview?.settings?.envDefaults

  const farmAnalytics = useMemo(() => {
    const s = stats || {}
    return [
      { id: 'growing', label: 'Растёт', value: s.growing, target: 'stats' },
      { id: 'ready', label: 'Готово', value: s.ready, target: 'stats' },
      { id: 'withered', label: 'Засохло', value: s.withered, target: 'stats' },
      { id: 'empty', label: 'Пусто', value: s.empty, target: 'stats' },
      { id: 'harvests', label: 'Урожаев', value: s.harvests ?? s.ready, target: 'player' },
      { id: 'crops', label: 'Культур', value: crops.length, target: 'crops' },
    ]
  }, [stats, crops.length])

  const focusSection = (target, id) => {
    setFarmFocus((prev) => (prev === id ? null : id))
    if (activeTab !== 'plots') setTab('plots')
    requestAnimationFrame(() => {
      const el = document.querySelector(`[data-farm-section="${target}"]`)
      el?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' })
    })
  }

  return (
    <div className="panel-farm">
      <AdminActionModal
        open={resetTarget != null}
        title={
          resetTarget === 'all'
            ? `Сбросить все грядки игрока ${playerFarm?.userId ?? ''}?`
            : `Сбросить грядку #${resetTarget}?`
        }
        description="Грядка станет пустой, урожай и таймеры пропадут."
        confirmText="Сбросить"
        danger
        loading={resettingPlot != null}
        onConfirm={confirmReset}
        onCancel={() => {
          if (resettingPlot == null) setResetTarget(null)
        }}
      />
      <AdminActionModal
        open={globalResetOpen}
        title="Глобальный рестарт фермы?"
        description="Все грядки всех игроков станут пустыми. Урожай и таймеры пропадут. Это необратимо."
        confirmText="Сбросить всё"
        danger
        loading={globalResetting}
        showPassword
        passwordRequired
        password={globalResetPassword}
        onPasswordChange={setGlobalResetPassword}
        passwordHint="бз3"
        onConfirm={confirmGlobalReset}
        onCancel={() => {
          if (!globalResetting) {
            setGlobalResetOpen(false)
            setGlobalResetPassword('')
          }
        }}
      />

      <article className="panel-shelf panel-shelf-page">
        <p className="panel-shelf-label">Farm · Ферма</p>
        <h2 className="panel-page-title">Управление фермой</h2>
        <p className="panel-page-lead">Рост культур, полив, грядки игроков и настройки семян</p>
        {error && <p className="panel-shelf-error">{error}</p>}
        {info && <p className="panel-users-info">{info}</p>}
      </article>

      <article className="panel-shelf panel-farm-online" aria-live="polite">
        <p className="panel-shelf-label">Онлайн на ферме</p>
        <p className="panel-stat-value">
          {online?.onlineNow != null ? Number(online.onlineNow).toLocaleString('ru-RU') : '—'}
        </p>
        <p className="panel-stat-hint">
          Пик сегодня: {online?.todayPeak != null ? Number(online.todayPeak).toLocaleString('ru-RU') : '—'}
        </p>
      </article>

      <div className="panel-farm-analytics" aria-label="Сводка фермы">
        <div className="panel-farm-analytics-periods" role="tablist" aria-label="Период">
          {[
            { id: 'day', label: 'День' },
            { id: 'month', label: 'Месяц' },
            { id: 'year', label: 'Год' },
          ].map((p) => (
            <button
              key={p.id}
              type="button"
              role="tab"
              aria-selected={farmPeriod === p.id}
              className={`panel-farm-analytics-period${farmPeriod === p.id ? ' is-on' : ''}`}
              onClick={() => setFarmPeriod(p.id)}
            >
              {p.label}
            </button>
          ))}
        </div>
        <p className="panel-shelf-muted" style={{ margin: 0 }}>
          Снимок сейчас — по периодам история пока не копится в API.
        </p>
        <div className="panel-farm-analytics-cards">
          {farmAnalytics.map((card) => (
            <button
              key={card.id}
              type="button"
              className={`panel-farm-analytics-card${farmFocus === card.id ? ' is-on' : ''}`}
              onClick={() => focusSection(card.target, card.id)}
            >
              <strong>{loading ? '…' : (card.value ?? '—')}</strong>
              <span>{card.label}</span>
            </button>
          ))}
        </div>
      </div>

      {tabs.length > 1 && (
        <div className="sys-tabs">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`sys-tab${activeTab === t.id ? ' active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}

      {activeTab === 'seed' && (
        <div className="sys-content">
          <SeedEconomySettings />
        </div>
      )}

      {activeTab === 'plots' && (
        <>
      <div
        className={`panel-economy-stats${farmFocus && ['growing', 'ready', 'withered', 'empty'].includes(farmFocus) ? ' panel-farm-highlight' : ''}`}
        data-farm-section="stats"
      >
        <article className="panel-shelf panel-economy-stat">
          <p className="panel-shelf-label">Грядок всего</p>
          <p className="panel-economy-stat-value">{loading ? '…' : stats?.totalPlots ?? '-'}</p>
          <p className="panel-shelf-muted">{stats?.playersWithPlots ?? 0} игроков</p>
        </article>
        <article className="panel-shelf panel-economy-stat">
          <p className="panel-shelf-label">Растёт</p>
          <p className="panel-economy-stat-value">{loading ? '…' : stats?.growing ?? '-'}</p>
          <p className="panel-shelf-muted">Готово: {stats?.ready ?? 0}</p>
        </article>
        <article className="panel-shelf panel-economy-stat">
          <p className="panel-shelf-label">Засохло</p>
          <p className="panel-economy-stat-value">{loading ? '…' : stats?.withered ?? '-'}</p>
          <p className="panel-shelf-muted">Пусто: {stats?.empty ?? 0}</p>
        </article>
      </div>

      <div className="panel-economy-grid-2">
        <article className="panel-shelf">
          <p className="panel-shelf-label">Настройки</p>
          <h3 className="panel-users-subtitle">Таймеры и лимиты</h3>
          {env && (
            <p className="panel-shelf-muted">
              Env: дерево {formatSec(env.treeGrowSeconds)}, табак {formatSec(env.tobaccoGrowSeconds)},
              грядок {env.maxPlots}
            </p>
          )}
          <div className="panel-economy-settings-form">
            <label className="panel-economy-field">
              <span>Дерево - рост (сек)</span>
              <input className="panel-users-input" value={treeGrow} onChange={(e) => setTreeGrow(e.target.value.replace(/[^\d]/g, ''))} disabled={loading || saving} />
              <span className="panel-shelf-muted">{formatSec(treeGrow)}</span>
            </label>
            <label className="panel-economy-field">
              <span>Табак - рост (сек)</span>
              <input className="panel-users-input" value={tobaccoGrow} onChange={(e) => setTobaccoGrow(e.target.value.replace(/[^\d]/g, ''))} disabled={loading || saving} />
              <span className="panel-shelf-muted">{formatSec(tobaccoGrow)}</span>
            </label>
            <label className="panel-economy-field">
              <span>Макс. грядок</span>
              <input className="panel-users-input" value={maxPlots} onChange={(e) => setMaxPlots(e.target.value.replace(/[^\d]/g, ''))} disabled={loading || saving} />
              <span className="panel-shelf-muted">До 100 · #1 бесплатна</span>
            </label>
            <label className="panel-economy-field">
              <span>Шаг цены грядки (кут)</span>
              <input className="panel-users-input" value={plotPriceStep} onChange={(e) => setPlotPriceStep(e.target.value.replace(/[^\d]/g, ''))} disabled={loading || saving} />
              <span className="panel-shelf-muted">#2 = 1×шаг, #3 = 2×шаг …</span>
            </label>
            <label className="panel-economy-field">
              <span>Очистка засохшей грядки</span>
              <input className="panel-users-input" value={clearCost} onChange={(e) => setClearCost(e.target.value.replace(/[^\d]/g, ''))} disabled={loading || saving} />
              <span className="panel-shelf-muted">кут за очистку</span>
            </label>
            <label className="panel-economy-field">
              <span>Интервал полива (сек)</span>
              <input className="panel-users-input" value={waterInterval} onChange={(e) => setWaterInterval(e.target.value.replace(/[^\d]/g, ''))} disabled={loading || saving} />
              <span className="panel-shelf-muted">{formatSec(waterInterval)}</span>
            </label>
            <label className="panel-economy-field">
              <span>Засуха - grace (сек)</span>
              <input className="panel-users-input" value={wiltGrace} onChange={(e) => setWiltGrace(e.target.value.replace(/[^\d]/g, ''))} disabled={loading || saving} />
              <span className="panel-shelf-muted">После «сухой земли» до wilt</span>
            </label>
            <label className="panel-economy-field">
              <span>Вода за полив (шт.)</span>
              <input className="panel-users-input" value={waterCost} onChange={(e) => setWaterCost(e.target.value.replace(/[^\d]/g, ''))} disabled={loading || saving} />
            </label>
            <button
              type="button"
              className="panel-users-btn panel-users-btn-primary panel-action-btn"
              disabled={loading || saving}
              onClick={handleSaveSettings}
            >
              {saving ? 'Сохраняем…' : 'Сохранить'}
            </button>
            {(error || info) && (
              <p className={`panel-action-notice${error ? ' panel-action-notice-error' : ' panel-action-notice-ok'}`}>
                {error || info}
              </p>
            )}
          </div>
        </article>

        <article className="panel-shelf">
          <p className="panel-shelf-label">Цены грядок</p>
          <h3 className="panel-users-subtitle">Предпросмотр</h3>
          <p className="panel-shelf-muted">
            {plotPreview.length
              ? `Грядка #${plotPreview[plotPreview.length - 1].plotId} = ${plotPreview[plotPreview.length - 1].price.toLocaleString('ru-RU')} кут`
              : 'Укажите макс. грядок и шаг цены'}
          </p>
          <ul className="panel-economy-plot-list panel-farm-plot-preview">
            {plotPreview.map((row) => (
              <li key={row.plotId}>
                <span>Грядка #{row.plotId}</span>
                <strong>{row.price.toLocaleString('ru-RU')} кут</strong>
              </li>
            ))}
          </ul>
        </article>

        <article
          className={`panel-shelf${farmFocus === 'crops' ? ' panel-farm-highlight' : ''}`}
          data-farm-section="crops"
        >
          <p className="panel-shelf-label">Культуры</p>
          <ul className="panel-economy-craft-list">
            {crops.map((crop) => (
              <li key={crop.key}>
                <span className="panel-economy-craft-title">
                  {crop.seedEmoji} {crop.seedName} → {crop.harvestEmoji} {crop.harvestName}
                </span>
                <span>Рост: {formatSec(crop.growSeconds)} · топор: {crop.requiresAxe ? 'да' : 'нет'}</span>
              </li>
            ))}
          </ul>
        </article>
      </div>

      <article
        className={`panel-shelf${farmFocus === 'harvests' ? ' panel-farm-highlight' : ''}`}
        data-farm-section="player"
      >
        <p className="panel-shelf-label">Грядки игрока</p>
        <form className="panel-users-search-form panel-farm-search" onSubmit={handlePlayerSearch}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <UserLookupPreview
              label="Игрок"
              value={playerQuery}
              onChange={(v) => { setPlayerQuery(v); setPlayerResolvedId(null) }}
              onResolved={(u) => setPlayerResolvedId(u ? Number(u.userId || u.user_id) : null)}
              onOpenUser={(id) => onOpenUser?.(id)}
              placeholder="ID, @username или имя"
            />
          </div>
          <button type="submit" className="panel-users-btn panel-users-btn-primary" disabled={playerLoading}>
            {playerLoading ? '…' : 'Найти'}
          </button>
        </form>

        {playerFarm && (
          <>
            <p className="panel-shelf-muted">
              {playerFarm.displayName}{' '}
              <IdentityBits userId={playerFarm.userId} username={playerFarm.username} />
              {' · '}{playerFarm.ownedPlots}/{playerFarm.maxPlots} грядок · вода: {playerFarm.waterCount ?? 0}
            </p>
            <div className="panel-users-plot-grid panel-farm-plot-grid">
              {playerFarm.plots.map((plot) => (
                <div key={plot.id} className="panel-users-plot">
                  <span className="panel-users-plot-id">#{plot.id}</span>
                  <span className="panel-users-plot-status">{PLOT_STATUS_LABEL[plot.status] || plot.status}</span>
                  {plot.cropId && <span className="panel-shelf-muted">{plot.cropId}</span>}
                  {plot.status !== 'EMPTY' && (
                    <button
                      type="button"
                      className="panel-users-btn panel-users-btn-danger"
                      disabled={resettingPlot === plot.id || resettingPlot === 'all'}
                      onClick={() => setResetTarget(plot.id)}
                    >
                      Сброс
                    </button>
                  )}
                </div>
              ))}
            </div>
            <button type="button" className="panel-users-btn panel-users-btn-danger" disabled={resettingPlot != null} onClick={() => setResetTarget('all')}>
              Сбросить все грядки игрока
            </button>
          </>
        )}
      </article>

      {isProjectCreator && (
        <article className="panel-shelf panel-farm-danger">
          <p className="panel-shelf-label">Осторожно</p>
          <h3 className="panel-users-subtitle">Глобальный рестарт фермы</h3>
          <p className="panel-shelf-muted">Очистит все грядки у всех игроков. Используй только при критической необходимости.</p>
          <button
            type="button"
            className="panel-users-btn panel-users-btn-danger"
            onClick={() => {
              setGlobalResetPassword('')
              setGlobalResetOpen(true)
            }}
          >
            Глобальный сброс
          </button>
        </article>
      )}
        </>
      )}
    </div>
  )
}
