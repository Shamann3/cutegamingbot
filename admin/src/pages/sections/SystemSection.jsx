import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchAllSettings,
  fetchSettingsHistory,
  saveAllSettings,
  setMaintenanceState,
} from '../../lib/adminClient'
import { notifyAdmin } from '../../lib/notify'
import { filterSectionTabs } from '../../constants/panelAccessTree'
import MemeSettings from '../../components/MemeSettings'

// Экономика, ферма и семена редактируются в EconomySection / FarmSection.
// Лейблы ниже — для вкладки «История».
const EXTRA_HISTORY_LABELS = {
  defaultBalance: 'Стартовый баланс (кут)',
  plotPriceStep: 'Шаг цены грядки',
  clearCost: 'Стоимость очистки грядки',
  treeGrowSeconds: 'Рост дерева (сек)',
  tobaccoGrowSeconds: 'Рост табака (сек)',
  maxPlots: 'Максимум грядок',
  waterIntervalSeconds: 'Интервал полива (сек)',
  wiltGraceSeconds: 'Засуха - отсрочка (сек)',
  waterCostPerUse: 'Расход воды за полив',
  harvestSeedDropPercent: 'Шанс вернуть семя при сборе (%)',
  dailySeedAmount: 'Ежедневное семя - количество',
  starterTreeSeeds: 'Стартовый набор: семена дерева',
  starterTobaccoSeeds: 'Стартовый набор: семена табака',
  starterWater: 'Стартовый набор: вода',
  starterAxe: 'Стартовый набор: топор',
}

const SETTING_GROUPS = [
  {
    id: 'system',
    label: 'Система',
    emoji: '⚙️',
    fields: [
      { key: 'adminSessionMinutes', label: 'Таймаут сессии администратора (мин)', type: 'int', hint: '5–1440 (1 день). Применяется к новым входам' },
    ],
  },
]

const CATEGORY_LABELS = {
  economy: '💰 Экономика',
  farm: '🌱 Ферма',
  seed: '🌿 Семена',
  system: '⚙️ Система',
}

const SETTING_LABELS = { ...EXTRA_HISTORY_LABELS }
SETTING_GROUPS.forEach((g) => g.fields.forEach((f) => { SETTING_LABELS[f.key] = f.label }))

function formatDate(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('ru-RU')
}

function formatSeconds(s) {
  if (s == null) return '-'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  if (h > 0) return `${h} ч ${m} мин`
  if (m > 0) return `${m} мин ${sec > 0 ? sec + ' с' : ''}`
  return `${sec} с`
}

function displayValue(key, value) {
  if (value == null || value === '') return '-'
  if (key.endsWith('Seconds')) return `${value} с (${formatSeconds(value)})`
  if (key === 'adminSessionMinutes') return `${value} мин`
  if (key.endsWith('Percent')) return `${value}%`
  if (key === 'defaultBalance' || key === 'plotPriceStep' || key === 'clearCost') {
    return `${Number(value).toLocaleString('ru-RU')} кут`
  }
  return String(value)
}

function SettingGroup({ group, effective, envDefaults, overrides, onSave, disabled }) {
  const [form, setForm] = useState({})
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    const init = {}
    group.fields.forEach(({ key }) => {
      init[key] = effective[key] != null ? String(effective[key]) : ''
    })
    setForm(init)
    setDirty(false)
  }, [effective, group.fields])

  const handleChange = (key, val) => {
    setForm((f) => ({ ...f, [key]: val }))
    setDirty(true)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const fields = {}
      group.fields.forEach(({ key }) => {
        const raw = form[key]
        if (raw !== '' && raw != null) {
          fields[key] = Number(raw)
        }
      })
      await onSave(fields)
      setDirty(false)
    } finally {
      setSaving(false)
    }
  }

  return (
    <article className="panel-shelf sys-group">
      <div className="sys-group-head">
        <span className="sys-group-emoji">{group.emoji}</span>
        <h3 className="sys-group-title">{group.label}</h3>
      </div>
      <div className="sys-fields">
        {group.fields.map(({ key, label, hint }) => {
          const envVal = envDefaults[key]
          const override = overrides[key]
          const isOverridden = override != null
          return (
            <div key={key} className={`sys-field${isOverridden ? ' overridden' : ''}`}>
              <label className="sys-field-label">
                {label}
                {isOverridden && <span className="sys-override-badge">override</span>}
              </label>
              <div className="sys-field-row">
                <input
                  className="panel-users-input sys-input"
                  type="number"
                  value={form[key] ?? ''}
                  onChange={(e) => handleChange(key, e.target.value)}
                  disabled={saving || disabled}
                />
                <span className="sys-field-env">env: {displayValue(key, envVal)}</span>
              </div>
              {hint && <p className="sys-field-hint">{hint}</p>}
            </div>
          )
        })}
      </div>
      <div className="sys-group-footer">
        <button
          className={`panel-users-btn panel-users-btn-primary${dirty ? '' : ' sys-btn-muted'}`}
          onClick={handleSave}
          disabled={saving || disabled || !dirty}
        >
          {saving ? 'Сохранение…' : 'Сохранить'}
        </button>
        {!dirty && <span className="sys-saved-hint">Сохранено</span>}
      </div>
    </article>
  )
}

function HistoryTab({ refreshKey }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [category, setCategory] = useState('')
  const [page, setPage] = useState(0)
  const limit = 30

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const d = await fetchSettingsHistory({
        category: category || null,
        limit,
        offset: page * limit,
      })
      setData(d)
    } catch (e) {
      notifyAdmin(e.message || 'Ошибка загрузки истории', { error: true })
    } finally {
      setLoading(false)
    }
  }, [category, page])

  useEffect(() => { load() }, [load, refreshKey])

  const totalPages = data ? Math.ceil(data.total / limit) : 0

  return (
    <div className="sys-history">
      <div className="sys-history-toolbar">
        <select
          className="panel-users-input sys-cat-select"
          value={category}
          onChange={(e) => { setCategory(e.target.value); setPage(0) }}
        >
          <option value="">Все категории</option>
          {Object.entries(CATEGORY_LABELS).map(([id, label]) => (
            <option key={id} value={id}>{label}</option>
          ))}
        </select>
        <span className="sys-history-total">Всего: {data?.total ?? '…'}</span>
      </div>

      {loading && <p className="panel-shelf-muted">Загрузка…</p>}

      {!loading && data && (
        <>
          {data.history.length === 0 && (
            <p className="panel-shelf-muted">Изменений не найдено</p>
          )}
          <div className="sys-history-list">
            {data.history.map((h) => (
              <div key={h.id} className="sys-history-row">
                <div className="sys-history-meta">
                  <span className={`sys-cat-tag cat-${h.category}`}>
                    {CATEGORY_LABELS[h.category] || h.category}
                  </span>
                  <time className="sys-history-time">{formatDate(h.createdAt)}</time>
                  <span className="sys-history-admin">Admin {h.adminUserId}</span>
                </div>
                <div className="sys-history-change">
                  <span className="sys-history-key">{SETTING_LABELS[h.settingKey] || h.settingKey}</span>
                  <span className="sys-history-val sys-history-old">{h.oldValue ?? '-'}</span>
                  <span className="sys-history-arrow">→</span>
                  <span className="sys-history-val sys-history-new">{h.newValue}</span>
                </div>
              </div>
            ))}
          </div>

          {totalPages > 1 && (
            <div className="sys-pagination">
              <button
                className="panel-users-btn"
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                ←
              </button>
              <span>{page + 1} / {totalPages}</span>
              <button
                className="panel-users-btn"
                disabled={page + 1 >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

/** Creator-only feature / maintenance switches. */
function CreatorTogglesPanel({ maintenance, onToggleMaintenance, saving }) {
  const on = Boolean(maintenance)
  return (
    <article className="panel-shelf sys-group creator-toggles">
      <div className="sys-group-head">
        <span className="sys-group-emoji">⏻</span>
        <h3 className="sys-group-title">Выключатели</h3>
      </div>
      <p className="panel-shelf-muted" style={{ margin: '0 0 1rem' }}>
        Только для создателя проекта. Каждый переключатель сразу меняет поведение для всех игроков.
      </p>
      <div className={`sys-toggle-row${on ? ' is-on' : ''}`}>
        <div className="sys-toggle-copy">
          <strong>Техработы всего сервера</strong>
          <em>
            Когда включено — игровой API отвечает режимом обслуживания: мини-приложение и игровые
            эндпоинты недоступны игрокам. Админ-панель продолжает работать.
          </em>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={on}
          className={`panel-toggle${on ? ' panel-toggle-on' : ''}`}
          disabled={saving}
          onClick={onToggleMaintenance}
        >
          <span className="panel-toggle-thumb" />
        </button>
      </div>
      <p className={`sys-toggle-status${on ? ' is-active' : ''}`}>
        {on ? 'Сейчас: сервер на техработах' : 'Сейчас: сервер открыт для игроков'}
      </p>
    </article>
  )
}

const BASE_TABS = [
  { id: 'system', label: '⚙️ Система' },
  { id: 'history', label: '📋 История' },
]

const TOGGLES_TAB = { id: 'toggles', label: '⏻ Выключатели' }

export default function SystemSection({ panelTabs = null, isProjectCreator = false }) {
  const tabs = useMemo(() => {
    const base = filterSectionTabs('settings', BASE_TABS, panelTabs)
    if (!isProjectCreator) return base
    // Creator toggles always available to project creator (not role-tab gated).
    const withoutDup = base.filter((t) => t.id !== 'toggles')
    return [TOGGLES_TAB, ...withoutDup]
  }, [panelTabs, isProjectCreator])

  const [tab, setTab] = useState(tabs[0]?.id || 'system')
  const activeTab = tabs.some((t) => t.id === tab) ? tab : tabs[0]?.id
  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0)
  const [maintenanceSaving, setMaintenanceSaving] = useState(false)

  const loadSettings = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const d = await fetchAllSettings()
      setSettings(d)
    } catch (e) {
      setError(e.message || 'Ошибка загрузки настроек')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadSettings() }, [loadSettings])

  useEffect(() => {
    if (tabs.length && !tabs.some((t) => t.id === tab)) {
      setTab(tabs[0].id)
    }
  }, [tabs, tab])

  const handleSave = useCallback(async (fields) => {
    try {
      const updated = await saveAllSettings(fields)
      setSettings(updated)
      setHistoryRefreshKey((k) => k + 1)
      notifyAdmin('Настройки сохранены')
    } catch (e) {
      notifyAdmin(e.message || 'Ошибка сохранения', { error: true })
      throw e
    }
  }, [])

  const handleMaintenanceToggle = useCallback(async () => {
    if (!settings) return
    setMaintenanceSaving(true)
    try {
      const newVal = !settings.maintenance
      await setMaintenanceState(newVal)
      setSettings((s) => ({ ...s, maintenance: newVal }))
      notifyAdmin(newVal ? 'Техработы включены' : 'Игра снова доступна')
    } catch (e) {
      notifyAdmin(e.message || 'Ошибка', { error: true })
    } finally {
      setMaintenanceSaving(false)
    }
  }, [settings])

  const eff = settings?.effective || {}
  const env = settings?.envDefaults || {}
  const overr = settings?.overrides || {}

  return (
    <div className="panel-settings">
      <article className="panel-shelf panel-shelf-page">
        <p className="panel-shelf-label">Settings · Настройки</p>
        <h2 className="panel-page-title">Системные настройки</h2>
        <p className="panel-page-lead">
          Конфигурация сессии и история изменений. Экономика, ферма и семена — в своих разделах.
          {isProjectCreator ? ' Выключатели обслуживания — только здесь, для создателя.' : ''}
        </p>
      </article>

      {error && <p className="panel-shelf-error" style={{ margin: '0 1rem 1rem' }}>{error}</p>}

      {settings && (
        <div className="sys-meta-bar">
          <span className="panel-shelf-muted">
            Последнее изменение: {settings.updatedAt ? formatDate(settings.updatedAt) : '-'}
            {settings.updatedBy ? ` · Admin ${settings.updatedBy}` : ''}
          </span>
        </div>
      )}

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

      {loading && <p className="panel-shelf-muted" style={{ padding: '1rem' }}>Загрузка…</p>}

      {!loading && settings && activeTab === 'toggles' && isProjectCreator && (
        <div className="sys-content">
          <CreatorTogglesPanel
            maintenance={settings.maintenance}
            onToggleMaintenance={handleMaintenanceToggle}
            saving={maintenanceSaving}
          />
          <MemeSettings />
        </div>
      )}

      {!loading && settings && activeTab && activeTab !== 'history' && activeTab !== 'toggles' && (
        <div className="sys-content">
          {SETTING_GROUPS.filter((g) => g.id === activeTab).map((group) => (
            <SettingGroup
              key={group.id}
              group={group}
              effective={eff}
              envDefaults={env}
              overrides={overr}
              onSave={handleSave}
              disabled={loading}
            />
          ))}
        </div>
      )}

      {!loading && activeTab === 'history' && (
        <div className="sys-content">
          <article className="panel-shelf">
            <p className="panel-shelf-label">История изменений</p>
            <HistoryTab refreshKey={historyRefreshKey} />
          </article>
        </div>
      )}
    </div>
  )
}
