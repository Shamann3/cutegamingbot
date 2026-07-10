import { useCallback, useEffect, useMemo, useState } from 'react'
import AdminActionModal from '../../components/AdminActionModal'
import {
  fetchFarmOverview,
  fetchFarmUser,
  globalFarmReset,
  resetFarmUserPlots,
  saveFarmSettings,
  searchAdminUsers,
} from '../../lib/adminClient'
import { parseRequiredIntFields } from '../../lib/formNumbers'
import { notifyAdmin } from '../../lib/notify'

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

export default function FarmSection() {
  const [overview, setOverview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')

  const [treeGrow, setTreeGrow] = useState('')
  const [tobaccoGrow, setTobaccoGrow] = useState('')
  const [maxPlots, setMaxPlots] = useState('')
  const [plotPriceStep, setPlotPriceStep] = useState('')
  const [waterInterval, setWaterInterval] = useState('')
  const [wiltGrace, setWiltGrace] = useState('')
  const [waterCost, setWaterCost] = useState('')

  const [playerQuery, setPlayerQuery] = useState('')
  const [playerFarm, setPlayerFarm] = useState(null)
  const [playerLoading, setPlayerLoading] = useState(false)
  const [resetTarget, setResetTarget] = useState(null)
  const [resettingPlot, setResettingPlot] = useState(null)
  const [globalResetOpen, setGlobalResetOpen] = useState(false)
  const [globalResetting, setGlobalResetting] = useState(false)

  const applySettings = useCallback((settings) => {
    if (!settings) return
    setTreeGrow(String(settings.treeGrowSeconds ?? ''))
    setTobaccoGrow(String(settings.tobaccoGrowSeconds ?? ''))
    setMaxPlots(String(settings.maxPlots ?? ''))
    setPlotPriceStep(String(settings.plotPriceStep ?? ''))
    setWaterInterval(String(settings.waterIntervalSeconds ?? ''))
    setWiltGrace(String(settings.wiltGraceSeconds ?? ''))
    setWaterCost(String(settings.waterCostPerUse ?? ''))
  }, [])

  const loadOverview = useCallback(async () => {
    setError('')
    try {
      const data = await fetchFarmOverview()
      setOverview(data)
      applySettings(data.settings)
    } catch (err) {
      setError(err.message || 'Не удалось загрузить ферму')
    } finally {
      setLoading(false)
    }
  }, [applySettings])

  useEffect(() => {
    loadOverview()
  }, [loadOverview])

  const handleSaveSettings = async () => {
    setError('')
    setInfo('')
    let payload
    try {
      payload = parseRequiredIntFields(
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
    } catch (err) {
      const message = err.message || 'Проверьте поля настроек'
      setError(message)
      notifyAdmin(message, { error: true })
      return
    }

    setSaving(true)
    try {
      const settings = await saveFarmSettings(payload)
      const message = `Сохранено. Макс. грядок: ${settings.maxPlots ?? payload.maxPlots}`
      setInfo(message)
      notifyAdmin(message)
      applySettings(settings)
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
    const q = playerQuery.trim()
    if (!q) return
    setPlayerLoading(true)
    setError('')
    try {
      if (/^\d+$/.test(q)) {
        await loadPlayer(Number(q))
        return
      }
      const data = await searchAdminUsers(q)
      const list = data.results || []
      if (list.length === 1) {
        await loadPlayer(list[0].userId)
      } else if (list.length === 0) {
        setPlayerFarm(null)
        setError('Никого не найдено')
      } else {
        setPlayerFarm(null)
        setError(`Найдено ${list.length} - уточни ID`)
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
    setGlobalResetting(true)
    setError('')
    setInfo('')
    try {
      const result = await globalFarmReset()
      setGlobalResetOpen(false)
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
        onConfirm={confirmGlobalReset}
        onCancel={() => {
          if (!globalResetting) setGlobalResetOpen(false)
        }}
      />

      <article className="panel-shelf panel-shelf-page">
        <p className="panel-shelf-label">Farm · Ферма</p>
        <h2 className="panel-page-title">Управление фермой</h2>
        <p className="panel-page-lead">Рост культур, полив, грядки игроков</p>
        {error && <p className="panel-shelf-error">{error}</p>}
        {info && <p className="panel-users-info">{info}</p>}
      </article>

      <div className="panel-economy-stats">
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
              <span>Шаг цены грядки (kut)</span>
              <input className="panel-users-input" value={plotPriceStep} onChange={(e) => setPlotPriceStep(e.target.value.replace(/[^\d]/g, ''))} disabled={loading || saving} />
              <span className="panel-shelf-muted">#2 = 1×шаг, #3 = 2×шаг …</span>
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
              ? `Грядка #${plotPreview[plotPreview.length - 1].plotId} = ${plotPreview[plotPreview.length - 1].price.toLocaleString('ru-RU')} kut`
              : 'Укажите макс. грядок и шаг цены'}
          </p>
          <ul className="panel-economy-plot-list panel-farm-plot-preview">
            {plotPreview.map((row) => (
              <li key={row.plotId}>
                <span>Грядка #{row.plotId}</span>
                <strong>{row.price.toLocaleString('ru-RU')} kut</strong>
              </li>
            ))}
          </ul>
        </article>

        <article className="panel-shelf">
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

      <article className="panel-shelf">
        <p className="panel-shelf-label">Грядки игрока</p>
        <form className="panel-users-search-form" onSubmit={handlePlayerSearch}>
          <input className="panel-users-input" value={playerQuery} onChange={(e) => setPlayerQuery(e.target.value)} placeholder="ID или @username" disabled={playerLoading} />
          <button type="submit" className="panel-users-btn panel-users-btn-primary" disabled={playerLoading}>
            {playerLoading ? '…' : 'Найти'}
          </button>
        </form>

        {playerFarm && (
          <>
            <p className="panel-shelf-muted">
              {playerFarm.displayName}
              {playerFarm.username && ` @${playerFarm.username}`} · {playerFarm.ownedPlots}/{playerFarm.maxPlots} грядок · вода: {playerFarm.waterCount ?? 0}
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

      <article className="panel-shelf panel-farm-danger">
        <p className="panel-shelf-label">Осторожно</p>
        <h3 className="panel-users-subtitle">Глобальный рестарт фермы</h3>
        <p className="panel-shelf-muted">Очистит все грядки у всех игроков. Используй только при критической необходимости.</p>
        <button type="button" className="panel-users-btn panel-users-btn-danger" onClick={() => setGlobalResetOpen(true)}>
          Глобальный сброс
        </button>
      </article>
    </div>
  )
}
