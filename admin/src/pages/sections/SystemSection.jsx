import { useCallback, useEffect, useState } from 'react'
import {
  fetchAllSettings,
  fetchSettingsHistory,
  saveAllSettings,
  setMaintenanceState,
} from '../../lib/adminClient'
import { notifyAdmin } from '../../lib/notify'
import { filterSectionTabs } from '../../constants/panelAccessTree'

// ---------------------------------------------------------------------------
// Metadata
// ---------------------------------------------------------------------------

// Экономика и Ферма редактируются только в EconomySection/FarmSection теперь
// (раньше те же поля можно было менять и здесь - без единого источника правды
// и без истории для правок через Economy/Farm). Лейблы для них оставлены в
// EXTRA_HISTORY_LABELS ниже, чтобы вкладка "История" продолжала показывать
// человекочитаемые названия для старых и новых записей категорий economy/farm.
const EXTRA_HISTORY_LABELS = {
  defaultBalance: 'Стартовый баланс (kut)',
  plotPriceStep: 'Шаг цены грядки',
  clearCost: 'Стоимость очистки грядки',
  treeGrowSeconds: 'Рост дерева (сек)',
  tobaccoGrowSeconds: 'Рост табака (сек)',
  maxPlots: 'Максимум грядок',
  waterIntervalSeconds: 'Интервал полива (сек)',
  wiltGraceSeconds: 'Засуха - отсрочка (сек)',
  waterCostPerUse: 'Расход воды за полив',
}

const SETTING_GROUPS = [
  {
    id: 'seed',
    label: 'Seed Economy',
    emoji: '🌿',
    fields: [
      { key: 'harvestSeedDropPercent', label: 'Шанс вернуть семя при сборе (%)', type: 'int', hint: '0–100, 0 = выключено' },
      { key: 'dailySeedAmount', label: 'Ежедневное семя - количество', type: 'int', hint: '1–50' },
      { key: 'starterTreeSeeds', label: 'Стартовый набор: семена дерева', type: 'int', hint: '0 = не выдавать' },
      { key: 'starterTobaccoSeeds', label: 'Стартовый набор: семена табака', type: 'int', hint: '0 = не выдавать' },
      { key: 'starterWater', label: 'Стартовый набор: вода', type: 'int', hint: '0 = не выдавать' },
      { key: 'starterAxe', label: 'Стартовый набор: топор', type: 'int', hint: '0 = не выдавать' },
    ],
  },
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
  seed: '🌿 Seed Economy',
  system: '⚙️ Система',
}

const SETTING_LABELS = { ...EXTRA_HISTORY_LABELS }
SETTING_GROUPS.forEach((g) => g.fields.forEach((f) => { SETTING_LABELS[f.key] = f.label }))

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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
    return `${Number(value).toLocaleString('ru-RU')} kut`
  }
  return String(value)
}

// ---------------------------------------------------------------------------
// SettingGroup component
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// History tab
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const TABS = [
  { id: 'seed', label: '🌿 Семена' },
  { id: 'system', label: '⚙️ Система' },
  { id: 'history', label: '📋 История' },
]

export default function SystemSection({ panelTabs = null }) {
  const tabs = filterSectionTabs('settings', TABS, panelTabs)
  const [tab, setTab] = useState(tabs[0]?.id || 'seed')
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
      notifyAdmin(newVal ? 'Режим обслуживания включён' : 'Режим обслуживания выключен')
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
          Единый экран конфигурации. Значения override .env без перезапуска сервера.
          Экономика и ферма редактируются в разделах «Экономика» и «Ферма» — здесь только их история изменений.
        </p>

        {settings && (
          <div className={`sys-maintenance-bar ${settings.maintenance ? 'active' : ''}`}>
            <span className="sys-maintenance-label">
              {settings.maintenance ? '🔴 Режим обслуживания активен' : '🟢 Сервер работает нормально'}
            </span>
            <button
              className={`panel-users-btn ${settings.maintenance ? 'panel-users-btn-success' : 'panel-users-btn-danger'}`}
              onClick={handleMaintenanceToggle}
              disabled={maintenanceSaving}
            >
              {maintenanceSaving ? '…' : settings.maintenance ? 'Выключить обслуживание' : 'Включить обслуживание'}
            </button>
          </div>
        )}
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
            className={`sys-tab${activeTab === t.id ? ' active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading && <p className="panel-shelf-muted" style={{ padding: '1rem' }}>Загрузка…</p>}

      {!loading && settings && activeTab && activeTab !== 'history' && (
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
