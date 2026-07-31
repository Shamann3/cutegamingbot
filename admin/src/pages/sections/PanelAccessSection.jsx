import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchPanelAccess,
  setPanelRoleDefault,
  setPanelUserAccess,
} from '../../lib/adminClient'

const GROUP_LABELS = {
  overview: 'Обзор',
  people: 'Игроки',
  economy: 'Экономика',
  content: 'Контент',
  team: 'Команда',
  insights: 'Аналитика',
  system: 'Система',
}

function memberName(m) {
  if (!m) return '—'
  return m.firstName || (m.username ? `@${m.username}` : `ID ${m.userId}`)
}

function Toggle({ on, disabled, onClick, label }) {
  return (
    <button
      type="button"
      className={`pa-toggle${on ? ' is-on' : ''}${disabled ? ' is-disabled' : ''}`}
      disabled={disabled}
      onClick={onClick}
      aria-pressed={on}
      title={label}
    >
      <span className="pa-toggle-knob" />
      <span className="pa-toggle-label">{on ? 'Вкл' : 'Выкл'}</span>
    </button>
  )
}

function StateChip({ state }) {
  if (state === 'grant') return <span className="pa-chip pa-chip-grant">выдано</span>
  if (state === 'deny') return <span className="pa-chip pa-chip-deny">запрет</span>
  return <span className="pa-chip pa-chip-default">дефолт</span>
}

export default function PanelAccessSection() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busyKey, setBusyKey] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [roleTab, setRoleTab] = useState('senior_admin')
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const d = await fetchPanelAccess()
      setData(d)
      setSelectedId((prev) => {
        if (prev && (d.members || []).some((m) => m.userId === prev)) return prev
        return d.members?.[0]?.userId ?? null
      })
    } catch (e) {
      setError(e?.message || 'Не удалось загрузить доступы')
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const configurableSections = useMemo(
    () => (data?.sections || []).filter((s) => s.configurable),
    [data],
  )

  const sectionsByGroup = useMemo(() => {
    const groups = []
    const seen = new Set()
    for (const s of configurableSections) {
      if (seen.has(s.group)) continue
      seen.add(s.group)
      groups.push({
        id: s.group,
        label: GROUP_LABELS[s.group] || s.group,
        items: configurableSections.filter((x) => x.group === s.group),
      })
    }
    return groups
  }, [configurableSections])

  const members = useMemo(() => {
    const q = query.trim().toLowerCase()
    const list = data?.members || []
    if (!q) return list
    return list.filter((m) => {
      const hay = `${m.firstName || ''} ${m.username || ''} ${m.userId} ${m.roleLabel || ''}`.toLowerCase()
      return hay.includes(q)
    })
  }, [data, query])

  const selected = useMemo(
    () => (data?.members || []).find((m) => m.userId === selectedId) || null,
    [data, selectedId],
  )

  const roleDefaults = data?.roleDefaults?.[roleTab] || {}

  const toggleRoleDefault = async (sectionId, enabled) => {
    const key = `role-${roleTab}-${sectionId}`
    setBusyKey(key)
    try {
      await setPanelRoleDefault({ role: roleTab, sectionId, enabled })
      await load()
    } catch (e) {
      alert(e?.message || 'Ошибка')
    } finally {
      setBusyKey(null)
    }
  }

  const setUserSection = async (sectionId, mode) => {
    if (!selected) return
    const key = `user-${selected.userId}-${sectionId}`
    setBusyKey(key)
    try {
      if (mode === 'default') {
        await setPanelUserAccess({ userId: selected.userId, sectionId, reset: true })
      } else {
        await setPanelUserAccess({
          userId: selected.userId,
          sectionId,
          allowed: mode === 'grant',
        })
      }
      await load()
    } catch (e) {
      alert(e?.message || 'Ошибка')
    } finally {
      setBusyKey(null)
    }
  }

  const sectionState = (sectionId) => {
    if (!selected) return { on: false, state: 'default' }
    const ov = selected.overrides?.[sectionId]
    if (ov === true) return { on: true, state: 'grant' }
    if (ov === false) return { on: false, state: 'deny' }
    const on = (selected.effectiveSections || []).includes(sectionId)
    return { on, state: 'default' }
  }

  return (
    <section className="panel-shelf panel-shelf-page pa-page">
      <header className="pa-hero">
        <div>
          <p className="pa-eyebrow">Только владелец</p>
          <h2 className="sec-title">Админ панель</h2>
          <p className="sec-desc">
            Дефолтные вкладки по ролям и персональные исключения для каждого администратора.
            Изменения применяются сразу — без перезапуска.
          </p>
        </div>
        <button type="button" className="sec-btn sec-btn-ghost" onClick={load} disabled={loading}>
          Обновить
        </button>
      </header>

      {loading && !data && <p className="sec-loading">Загрузка матрицы доступов…</p>}
      {error && <p className="sec-empty">{error}</p>}

      {data && (
        <div className="pa-layout">
          <aside className="pa-defaults elite-block">
            <div className="pa-block-head">
              <h3 className="pa-block-title">Дефолты ролей</h3>
              <p className="pa-block-sub">Базовый набор вкладок при выдаче роли</p>
            </div>
            <div className="pa-role-tabs" role="tablist">
              {(data.roles || []).map((r) => (
                <button
                  key={r.id}
                  type="button"
                  role="tab"
                  aria-selected={roleTab === r.id}
                  className={`pa-role-tab${roleTab === r.id ? ' is-active' : ''}`}
                  onClick={() => setRoleTab(r.id)}
                >
                  {r.label}
                </button>
              ))}
            </div>
            <div className="pa-section-groups">
              {sectionsByGroup.map((g) => (
                <div key={g.id} className="pa-group">
                  <p className="pa-group-label">{g.label}</p>
                  <ul className="pa-section-list">
                    {g.items.map((s) => {
                      const on = !!roleDefaults[s.id]
                      const busy = busyKey === `role-${roleTab}-${s.id}`
                      return (
                        <li key={s.id} className="pa-section-row">
                          <span className="pa-section-name">{s.label}</span>
                          <Toggle
                            on={on}
                            disabled={busy}
                            label={`${s.label}: ${on ? 'включено' : 'выключено'}`}
                            onClick={() => toggleRoleDefault(s.id, !on)}
                          />
                        </li>
                      )
                    })}
                  </ul>
                </div>
              ))}
            </div>
          </aside>

          <div className="pa-people elite-block">
            <div className="pa-block-head pa-block-head-row">
              <div>
                <h3 className="pa-block-title">Администраторы</h3>
                <p className="pa-block-sub">Персонально открыть или закрыть вкладку поверх дефолта</p>
              </div>
              <input
                className="sec-input pa-search"
                placeholder="Поиск…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>

            <div className="pa-people-split">
              <ul className="pa-member-list">
                {members.map((m) => (
                  <li key={m.userId}>
                    <button
                      type="button"
                      className={`pa-member${selectedId === m.userId ? ' is-active' : ''}`}
                      onClick={() => setSelectedId(m.userId)}
                    >
                      <span className="pa-member-name">{memberName(m)}</span>
                      <span className="pa-member-meta">{m.roleLabel}</span>
                      <span className="pa-member-count">
                        {(m.effectiveSections || []).length} вкладок
                      </span>
                    </button>
                  </li>
                ))}
                {members.length === 0 && (
                  <li className="pa-empty">Никого не найдено</li>
                )}
              </ul>

              <div className="pa-member-detail">
                {!selected && <p className="sec-empty">Выберите администратора</p>}
                {selected && (
                  <>
                    <div className="pa-detail-head">
                      <div>
                        <h4 className="pa-detail-name">{memberName(selected)}</h4>
                        <p className="pa-detail-meta">
                          {selected.roleLabel}
                          {selected.username ? ` · @${selected.username}` : ''}
                          {` · ID ${selected.userId}`}
                        </p>
                      </div>
                      <button
                        type="button"
                        className="sec-btn sec-btn-ghost sec-btn-sm"
                        disabled={busyKey?.startsWith(`user-${selected.userId}`)}
                        onClick={async () => {
                          if (!confirm('Сбросить все персональные исключения к дефолту роли?')) return
                          setBusyKey(`user-${selected.userId}-reset`)
                          try {
                            const overs = Object.keys(selected.overrides || {})
                            for (const sectionId of overs) {
                              await setPanelUserAccess({
                                userId: selected.userId,
                                sectionId,
                                reset: true,
                              })
                            }
                            await load()
                          } catch (e) {
                            alert(e?.message || 'Ошибка')
                          } finally {
                            setBusyKey(null)
                          }
                        }}
                      >
                        Сбросить исключения
                      </button>
                    </div>

                    <div className="pa-section-groups">
                      {sectionsByGroup.map((g) => (
                        <div key={g.id} className="pa-group">
                          <p className="pa-group-label">{g.label}</p>
                          <ul className="pa-section-list">
                            {g.items.map((s) => {
                              const { on, state } = sectionState(s.id)
                              const busy = busyKey === `user-${selected.userId}-${s.id}`
                              return (
                                <li key={s.id} className="pa-section-row pa-section-row-user">
                                  <div className="pa-section-who">
                                    <span className="pa-section-name">{s.label}</span>
                                    <StateChip state={state} />
                                  </div>
                                  <div className="pa-user-actions">
                                    <button
                                      type="button"
                                      className={`pa-pill${state === 'grant' ? ' is-on' : ''}`}
                                      disabled={busy}
                                      onClick={() => setUserSection(s.id, 'grant')}
                                    >
                                      Выдать
                                    </button>
                                    <button
                                      type="button"
                                      className={`pa-pill${state === 'default' ? ' is-on' : ''}`}
                                      disabled={busy}
                                      onClick={() => setUserSection(s.id, 'default')}
                                    >
                                      Дефолт
                                    </button>
                                    <button
                                      type="button"
                                      className={`pa-pill pa-pill-danger${state === 'deny' ? ' is-on' : ''}`}
                                      disabled={busy}
                                      onClick={() => setUserSection(s.id, 'deny')}
                                    >
                                      Запрет
                                    </button>
                                    <span className={`pa-eff${on ? ' is-on' : ''}`} title="Итоговый доступ">
                                      {on ? 'открыто' : 'закрыто'}
                                    </span>
                                  </div>
                                </li>
                              )
                            })}
                          </ul>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
