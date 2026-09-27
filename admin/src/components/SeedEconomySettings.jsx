import { useCallback, useEffect, useState } from 'react'
import { fetchAllSettings, saveAllSettings } from '../lib/adminClient'
import { notifyAdmin } from '../lib/notify'

const SEED_FIELDS = [
  { key: 'harvestSeedDropPercent', label: 'Шанс вернуть семя при сборе (%)', hint: '0–100, 0 = выключено' },
  { key: 'dailySeedAmount', label: 'Ежедневное семя — количество', hint: '1–50' },
  { key: 'starterTreeSeeds', label: 'Стартовый набор: семена дерева', hint: '0 = не выдавать' },
  { key: 'starterTobaccoSeeds', label: 'Стартовый набор: семена табака', hint: '0 = не выдавать' },
  { key: 'starterWater', label: 'Стартовый набор: вода', hint: '0 = не выдавать' },
  { key: 'starterAxe', label: 'Стартовый набор: топор', hint: '0 = не выдавать' },
]

function displayValue(key, value) {
  if (value == null || value === '') return '-'
  if (key.endsWith('Percent')) return `${value}%`
  return String(value)
}

/** Настройки Seed Economy — раньше жили во вкладке «Семена» в SystemSection. */
export default function SeedEconomySettings() {
  const [settings, setSettings] = useState(null)
  const [form, setForm] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const d = await fetchAllSettings()
      setSettings(d)
      const eff = d?.effective || {}
      const init = {}
      SEED_FIELDS.forEach(({ key }) => {
        init[key] = eff[key] != null ? String(eff[key]) : ''
      })
      setForm(init)
      setDirty(false)
    } catch (e) {
      setError(e.message || 'Ошибка загрузки настроек семян')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleSave = async () => {
    setSaving(true)
    try {
      const fields = {}
      SEED_FIELDS.forEach(({ key }) => {
        const raw = form[key]
        if (raw !== '' && raw != null) fields[key] = Number(raw)
      })
      const updated = await saveAllSettings(fields)
      setSettings(updated)
      setDirty(false)
      notifyAdmin('Настройки семян сохранены')
    } catch (e) {
      notifyAdmin(e.message || 'Ошибка сохранения', { error: true })
    } finally {
      setSaving(false)
    }
  }

  const eff = settings?.effective || {}
  const env = settings?.envDefaults || {}
  const overr = settings?.overrides || {}

  return (
    <article className="panel-shelf sys-group">
      <div className="sys-group-head">
        <span className="sys-group-emoji">🌿</span>
        <h3 className="sys-group-title">Семена</h3>
      </div>
      <p className="panel-shelf-muted" style={{ margin: '0 0 0.75rem' }}>
        Шанс дропа, ежедневная выдача и стартовый набор. Переопределяет .env без перезапуска.
      </p>
      {error && <p className="panel-shelf-error">{error}</p>}
      {loading && <p className="panel-shelf-muted">Загрузка…</p>}
      {!loading && settings && (
        <>
          <div className="sys-fields">
            {SEED_FIELDS.map(({ key, label, hint }) => {
              const isOverridden = overr[key] != null
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
                      onChange={(e) => {
                        setForm((f) => ({ ...f, [key]: e.target.value }))
                        setDirty(true)
                      }}
                      disabled={saving}
                    />
                    <span className="sys-field-env">env: {displayValue(key, env[key] ?? eff[key])}</span>
                  </div>
                  {hint && <p className="sys-field-hint">{hint}</p>}
                </div>
              )
            })}
          </div>
          <div className="sys-group-footer">
            <button
              type="button"
              className={`panel-users-btn panel-users-btn-primary${dirty ? '' : ' sys-btn-muted'}`}
              onClick={handleSave}
              disabled={saving || !dirty}
            >
              {saving ? 'Сохранение…' : 'Сохранить'}
            </button>
            {!dirty && <span className="sys-saved-hint">Сохранено</span>}
          </div>
        </>
      )}
    </article>
  )
}
