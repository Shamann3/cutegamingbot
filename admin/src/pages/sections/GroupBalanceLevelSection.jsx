import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchGroupBalanceLevelOverview,
  fetchGroupBalanceLevelChat,
  resetGroupBalanceLevelSettings,
  saveGroupBalanceLevelSettings,
  setGroupBalanceLevelChat,
} from '../../lib/adminClient'
import { notifyAdmin } from '../../lib/notify'

const LEVELS = [1, 2, 3, 4, 5]

function stars(n) {
  const v = Math.max(0, Math.min(5, Number(n) || 0))
  return `${'★'.repeat(v)}${'☆'.repeat(5 - v)}`
}

function Field({ label, help, children }) {
  return (
    <label className="gbl-field">
      <span className="gbl-field-label">{label}</span>
      {help ? <span className="gbl-field-help">{help}</span> : null}
      <div className="gbl-field-control">{children}</div>
    </label>
  )
}

export default function GroupBalanceLevelSection() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [settings, setSettings] = useState(null)
  const [help, setHelp] = useState({})
  const [recent, setRecent] = useState([])
  const [tab, setTab] = useState('core')
  const [chatId, setChatId] = useState('')
  const [chatLevel, setChatLevel] = useState(0)
  const [chatInfo, setChatInfo] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchGroupBalanceLevelOverview()
      setSettings(data.settings || {})
      setHelp(data.param_help || {})
      setRecent(Array.isArray(data.recent) ? data.recent : [])
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const prices = settings?.prices || {}
  const caps = settings?.stake_caps || {}
  const badges = settings?.badge_titles || {}

  const patchLocal = (key, value) => {
    setSettings((prev) => ({ ...(prev || {}), [key]: value }))
  }

  const patchMap = (mapKey, entryKey, value) => {
    setSettings((prev) => ({
      ...(prev || {}),
      [mapKey]: { ...((prev || {})[mapKey] || {}), [String(entryKey)]: value },
    }))
  }

  const onSave = async () => {
    if (!settings) return
    setSaving(true)
    try {
      const payload = {
        enabled: !!settings.enabled,
        level_0_cap: Number(settings.level_0_cap) || 0,
        recommend_pct: Number(settings.recommend_pct) || 0,
        health_success_min: Number(settings.health_success_min) || 0,
        health_primary_min: Number(settings.health_primary_min) || 0,
        atmosphere_enabled: !!settings.atmosphere_enabled,
        atmosphere_max_bonus_pct: Number(settings.atmosphere_max_bonus_pct) || 0,
        raise_button_text: String(settings.raise_button_text || '').slice(0, 64),
        system_title: String(settings.system_title || '').slice(0, 128),
        prices: Object.fromEntries(
          LEVELS.map((n) => [String(n), Math.max(0, Number(prices[String(n)]) || 0)]),
        ),
        stake_caps: Object.fromEntries(
          LEVELS.map((n) => {
            const raw = caps[String(n)]
            if (n === 5 && (raw === '' || raw === null || raw === undefined)) return [String(n), null]
            if (raw === '' || raw === null || raw === undefined) return [String(n), null]
            return [String(n), Math.max(0, Number(raw) || 0)]
          }),
        ),
        badge_titles: Object.fromEntries(
          LEVELS.map((n) => [String(n), String(badges[String(n)] || '').slice(0, 80)]),
        ),
      }
      const res = await saveGroupBalanceLevelSettings(payload)
      setSettings(res.settings || payload)
      notifyAdmin('Параметры уровней баланса группы сохранены')
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    } finally {
      setSaving(false)
    }
  }

  const onReset = async () => {
    if (!window.confirm('Сбросить все параметры уровней к значениям по умолчанию?')) return
    setSaving(true)
    try {
      const res = await resetGroupBalanceLevelSettings()
      setSettings(res.settings || {})
      notifyAdmin('Сброшено к defaults')
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    } finally {
      setSaving(false)
    }
  }

  const onLookupChat = async () => {
    const id = Number(String(chatId).trim())
    if (!Number.isFinite(id)) {
      notifyAdmin('Укажите chat_id', { error: true })
      return
    }
    try {
      const info = await fetchGroupBalanceLevelChat(id)
      setChatInfo(info)
      setChatLevel(Number(info.level) || 0)
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    }
  }

  const onSetChat = async () => {
    const id = Number(String(chatId).trim())
    if (!Number.isFinite(id)) return
    try {
      const res = await setGroupBalanceLevelChat(id, chatLevel)
      setChatInfo((prev) => ({ ...(prev || {}), ...res, stars: stars(res.level) }))
      notifyAdmin(`${id} → ${stars(res.level)}`)
      load()
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    }
  }

  const recentRows = useMemo(() => recent.slice(0, 30), [recent])

  if (loading || !settings) {
    return (
      <article className="panel-shelf panel-shelf-page gbl-page">
        <p className="panel-shelf-label">Owner only</p>
        <h2 className="panel-page-title">Уровни баланса группы</h2>
        <p className="panel-page-lead">Загрузка…</p>
      </article>
    )
  }

  return (
    <article className="panel-shelf panel-shelf-page gbl-page">
      <div className="gbl-hero">
        <p className="panel-shelf-label">Owner only · ч/б студия</p>
        <h2 className="panel-page-title">Уровни баланса группы</h2>
        <p className="panel-page-lead">
          Студия ★1–★5: цены шагов, потолки ставок, здоровье кнопки «бч», именные метки.
          В игровых текстах везде «баланс группы» — уважительно и без слова «стол».
        </p>
        <div className="gbl-hero-actions">
          <button type="button" className="elite-btn elite-btn-primary" disabled={saving} onClick={onSave}>
            {saving ? 'Сохраняю…' : 'Сохранить'}
          </button>
          <button type="button" className="elite-btn" disabled={saving} onClick={onReset}>
            Сброс defaults
          </button>
          <button type="button" className="elite-btn" disabled={saving} onClick={load}>
            Обновить
          </button>
        </div>
      </div>

      <div className="gbl-tabs" role="tablist">
        {[
          ['core', 'Ядро'],
          ['levels', 'Уровни'],
          ['health', 'Здоровье бч'],
          ['badges', 'Метки'],
          ['manual', 'Ручная выдача'],
          ['log', 'Покупки'],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`gbl-tab${tab === id ? ' gbl-tab-active' : ''}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="gbl-scroll">
        {tab === 'core' && (
          <div className="gbl-grid">
            <Field label="Система включена" help={help.enabled}>
              <input
                type="checkbox"
                checked={!!settings.enabled}
                onChange={(e) => patchLocal('enabled', e.target.checked)}
              />
            </Field>
            <Field label="Лимит при ★0" help={help.level_0_cap}>
              <input
                type="number"
                min={0}
                value={settings.level_0_cap ?? 30}
                onChange={(e) => patchLocal('level_0_cap', e.target.value)}
              />
            </Field>
            <Field label="Рекомендуемая ставка, %" help={help.recommend_pct}>
              <input
                type="number"
                min={0}
                max={100}
                step={0.5}
                value={settings.recommend_pct ?? 15}
                onChange={(e) => patchLocal('recommend_pct', e.target.value)}
              />
            </Field>
            <Field label="Текст кнопки апгрейда" help={help.raise_button_text}>
              <input
                type="text"
                maxLength={64}
                value={settings.raise_button_text || ''}
                onChange={(e) => patchLocal('raise_button_text', e.target.value)}
              />
            </Field>
            <Field label="Атмосфера" help={help.atmosphere_enabled}>
              <input
                type="checkbox"
                checked={!!settings.atmosphere_enabled}
                onChange={(e) => patchLocal('atmosphere_enabled', e.target.checked)}
              />
            </Field>
            <Field label="Макс. бонус атмосферы %" help={help.atmosphere_max_bonus_pct}>
              <input
                type="number"
                min={0}
                max={200}
                value={settings.atmosphere_max_bonus_pct ?? 40}
                onChange={(e) => patchLocal('atmosphere_max_bonus_pct', e.target.value)}
              />
            </Field>
          </div>
        )}

        {tab === 'levels' && (
          <div className="gbl-levels">
            {LEVELS.map((n) => (
              <div key={n} className="gbl-level-card">
                <div className="gbl-level-head">{stars(n)} · уровень {n}</div>
                <Field label="Цена шага (★)" help={help.prices}>
                  <input
                    type="number"
                    min={0}
                    value={prices[String(n)] ?? ''}
                    onChange={(e) => patchMap('prices', n, e.target.value)}
                  />
                </Field>
                <Field
                  label={n === 5 ? 'Лимит ставки (пусто = без лимита)' : 'Лимит ставки'}
                  help={help.stake_caps}
                >
                  <input
                    type="number"
                    min={0}
                    placeholder={n === 5 ? 'без лимита' : ''}
                    value={caps[String(n)] ?? ''}
                    onChange={(e) => patchMap('stake_caps', n, e.target.value === '' ? '' : e.target.value)}
                  />
                </Field>
              </div>
            ))}
          </div>
        )}

        {tab === 'health' && (
          <div className="gbl-grid">
            <Field label="Success порог (ratio)" help={help.health_success_min}>
              <input
                type="number"
                min={0}
                step={0.05}
                value={settings.health_success_min ?? 1}
                onChange={(e) => patchLocal('health_success_min', e.target.value)}
              />
            </Field>
            <Field label="Primary порог (ratio)" help={help.health_primary_min}>
              <input
                type="number"
                min={0}
                step={0.05}
                value={settings.health_primary_min ?? 0.4}
                onChange={(e) => patchLocal('health_primary_min', e.target.value)}
              />
            </Field>
            <p className="gbl-note">
              ratio = (бч × recommend_pct / 100) / лимит_уровня.
              Выше success → зелёная кнопка бч; между primary и success → primary; ниже → danger.
            </p>
          </div>
        )}

        {tab === 'badges' && (
          <div className="gbl-levels">
            {LEVELS.map((n) => (
              <div key={n} className="gbl-level-card">
                <div className="gbl-level-head">{stars(n)}</div>
                <Field label="Метка в профиле" help={help.badge_titles}>
                  <input
                    type="text"
                    maxLength={80}
                    value={badges[String(n)] || ''}
                    onChange={(e) => patchMap('badge_titles', n, e.target.value)}
                  />
                </Field>
              </div>
            ))}
          </div>
        )}

        {tab === 'manual' && (
          <div className="gbl-grid">
            <Field label="chat_id группы" help="Можно выдать любой уровень вручную (в т.ч. официальной).">
              <input type="text" value={chatId} onChange={(e) => setChatId(e.target.value)} placeholder="-100…" />
            </Field>
            <div className="gbl-inline-actions">
              <button type="button" className="elite-btn" onClick={onLookupChat}>Смотреть</button>
            </div>
            <Field label="Уровень 0…5">
              <input
                type="number"
                min={0}
                max={5}
                value={chatLevel}
                onChange={(e) => setChatLevel(Number(e.target.value) || 0)}
              />
            </Field>
            <div className="gbl-inline-actions">
              <button type="button" className="elite-btn elite-btn-primary" onClick={onSetChat}>
                Выставить уровень
              </button>
            </div>
            {chatInfo ? (
              <pre className="gbl-pre">{JSON.stringify(chatInfo, null, 2)}</pre>
            ) : null}
          </div>
        )}

        {tab === 'log' && (
          <div className="gbl-log">
            {recentRows.length === 0 ? (
              <p className="gbl-note">Покупок пока нет.</p>
            ) : (
              recentRows.map((ev, idx) => (
                <div key={`${ev.ts}-${idx}`} className="gbl-log-row">
                  <span>{stars(ev.level)}</span>
                  <span>chat {ev.chat_id}</span>
                  <span>user {ev.user_id}</span>
                  <span>{ev.price_stars}★</span>
                  <span className="gbl-log-ts">
                    {ev.ts ? new Date(ev.ts * 1000).toLocaleString('ru-RU') : '—'}
                  </span>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </article>
  )
}
