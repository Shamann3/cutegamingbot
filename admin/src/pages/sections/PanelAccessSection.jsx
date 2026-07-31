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

const TABS = [
  { id: 'defaults', label: 'Дефолты ролей' },
  { id: 'members', label: 'Администраторы' },
  { id: 'compare', label: 'Сравнение' },
]

function memberName(m) {
  if (!m) return '—'
  return m.firstName || (m.username ? `@${m.username}` : `ID ${m.userId}`)
}

function shortName(m) {
  const full = memberName(m)
  return full.length > 14 ? `${full.slice(0, 12)}…` : full
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
      <span className="pa-toggle-track" aria-hidden="true">
        <span className="pa-toggle-knob" />
      </span>
      <span className="pa-toggle-label">{on ? 'Вкл' : 'Выкл'}</span>
    </button>
  )
}

function StateChip({ state }) {
  if (state === 'grant') return <span className="pa-chip pa-chip-grant">выдано</span>
  if (state === 'deny') return <span className="pa-chip pa-chip-deny">запрет</span>
  return <span className="pa-chip pa-chip-default">дефолт</span>
}

function HelpModal({ onClose }) {
  return (
    <div className="admin-modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="admin-modal pa-help-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="pa-help-title"
        onClick={(e) => e.stopPropagation()}
      >
        <p className="pa-help-kicker">ACCESS · GUIDE</p>
        <h3 id="pa-help-title" className="admin-modal-title">Что это за вкладка</h3>
        <p className="admin-modal-desc">
          «Админ панель» — центр управления видимостью разделов панели.
          Доступна только владельцу. Изменения применяются сразу, без перезапуска.
        </p>

        <ul className="pa-help-list">
          <li>
            <strong>Дефолты ролей</strong>
            <span>
              Базовый набор вкладок для старшего, младшего и модератора.
              Выдаёте роль — человек сразу получает эти разделы.
            </span>
          </li>
          <li>
            <strong>Администраторы</strong>
            <span>
              Персональные исключения поверх дефолта: Выдать / Дефолт / Запрет
              для каждой вкладки у конкретного человека.
            </span>
          </li>
          <li>
            <strong>Сравнение</strong>
            <span>
              Матрица доступов: сравните всех или выбранных администраторов
              по вкладкам, подсветите только отличия.
            </span>
          </li>
        </ul>

        <p className="pa-help-note">
          Итоговый доступ = дефолт роли ± персональные исключения.
          Вкладка «Админ панель» у других ролей недоступна.
        </p>

        <div className="admin-modal-actions">
          <button type="button" className="panel-users-btn panel-users-btn-primary" data-modal-confirm onClick={onClose}>
            Понятно
          </button>
        </div>
      </div>
    </div>
  )
}

function ComparePane({ allMembers, sectionsByGroup, configurableSections }) {
  const [picked, setPicked] = useState(() => new Set())
  const [onlyDiff, setOnlyDiff] = useState(false)
  const [roleFilter, setRoleFilter] = useState('all')

  const pool = useMemo(() => {
    if (roleFilter === 'all') return allMembers
    return allMembers.filter((m) => m.role === roleFilter)
  }, [allMembers, roleFilter])

  // При смене фильтра — убираем из выбора тех, кого больше нет в пуле
  useEffect(() => {
    setPicked((prev) => {
      const allowed = new Set(pool.map((m) => m.userId))
      const next = new Set([...prev].filter((id) => allowed.has(id)))
      return next.size === prev.size ? prev : next
    })
  }, [pool])

  const selected = useMemo(
    () => pool.filter((m) => picked.has(m.userId)),
    [pool, picked],
  )

  const toggle = (id) => {
    setPicked((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const selectAll = () => setPicked(new Set(pool.map((m) => m.userId)))
  const clearAll = () => setPicked(new Set())

  const matrixRows = useMemo(() => {
    const rows = []
    for (const g of sectionsByGroup) {
      for (const s of g.items) {
        const cells = selected.map((m) => ({
          userId: m.userId,
          open: (m.effectiveSections || []).includes(s.id),
          override: m.overrides?.[s.id],
        }))
        const opens = cells.map((c) => c.open)
        const hasDiff = opens.length > 1 && new Set(opens.map(Boolean)).size > 1
        rows.push({
          sectionId: s.id,
          label: s.label,
          group: g.label,
          cells,
          hasDiff,
          openCount: opens.filter(Boolean).length,
        })
      }
    }
    return onlyDiff ? rows.filter((r) => r.hasDiff) : rows
  }, [sectionsByGroup, selected, onlyDiff])

  const diffCount = useMemo(() => {
    if (selected.length < 2) return 0
    let n = 0
    for (const s of configurableSections) {
      const opens = selected.map((m) => (m.effectiveSections || []).includes(s.id))
      if (new Set(opens.map(Boolean)).size > 1) n += 1
    }
    return n
  }, [selected, configurableSections])

  return (
    <div className="pa-pane pa-pane-compare">
      <div className="pa-cyber">
        <div className="pa-cyber-scan" aria-hidden="true" />
        <header className="pa-cyber-head">
          <div>
            <p className="pa-cyber-kicker">ACCESS MATRIX // COMPARE</p>
            <h3 className="pa-cyber-title">Сравнение доступов</h3>
            <p className="pa-cyber-sub">
              Выберите администраторов — матрица покажет, у кого какая вкладка открыта.
            </p>
          </div>
          <div className="pa-cyber-meters" aria-hidden="true">
            <span className="pa-cyber-meter">
              <b>{selected.length}</b>
              <em>выбрано</em>
            </span>
            <span className="pa-cyber-meter">
              <b>{diffCount}</b>
              <em>отличий</em>
            </span>
            <span className="pa-cyber-meter">
              <b>{configurableSections.length}</b>
              <em>вкладок</em>
            </span>
          </div>
        </header>

        <div className="pa-cyber-controls">
          <div className="pa-cyber-filters">
            <button
              type="button"
              className={`pa-cyber-chip${roleFilter === 'all' ? ' is-on' : ''}`}
              onClick={() => setRoleFilter('all')}
            >
              Все роли
            </button>
            <button
              type="button"
              className={`pa-cyber-chip${roleFilter === 'senior_admin' ? ' is-on' : ''}`}
              onClick={() => setRoleFilter('senior_admin')}
            >
              Старшие
            </button>
            <button
              type="button"
              className={`pa-cyber-chip${roleFilter === 'junior_admin' ? ' is-on' : ''}`}
              onClick={() => setRoleFilter('junior_admin')}
            >
              Младшие
            </button>
            <button
              type="button"
              className={`pa-cyber-chip${roleFilter === 'moderator' ? ' is-on' : ''}`}
              onClick={() => setRoleFilter('moderator')}
            >
              Модераторы
            </button>
          </div>
          <div className="pa-cyber-actions">
            <button type="button" className="pa-cyber-chip" onClick={selectAll} disabled={!pool.length}>
              Выбрать всех
            </button>
            <button type="button" className="pa-cyber-chip" onClick={clearAll} disabled={!picked.size}>
              Очистить
            </button>
            <button
              type="button"
              className={`pa-cyber-chip${onlyDiff ? ' is-on' : ''}`}
              onClick={() => setOnlyDiff((v) => !v)}
              disabled={selected.length < 2}
            >
              Только отличия
            </button>
          </div>
        </div>

        <div className="pa-cyber-pick">
          {pool.length === 0 && (
            <p className="pa-empty">Нет администраторов в этом фильтре</p>
          )}
          {pool.map((m) => {
            const on = picked.has(m.userId)
            const n = (m.effectiveSections || []).length
            return (
              <button
                key={m.userId}
                type="button"
                className={`pa-cyber-person${on ? ' is-on' : ''}`}
                onClick={() => toggle(m.userId)}
                aria-pressed={on}
              >
                <span className="pa-cyber-person-mark" aria-hidden="true">{on ? '▣' : '□'}</span>
                <span className="pa-cyber-person-body">
                  <span className="pa-cyber-person-name">{memberName(m)}</span>
                  <span className="pa-cyber-person-meta">
                    {m.roleLabel} · {n}/{configurableSections.length}
                  </span>
                </span>
              </button>
            )
          })}
        </div>

        {selected.length === 0 && (
          <div className="pa-cyber-empty">
            <p>Выберите хотя бы одного администратора</p>
            <span>или нажмите «Выбрать всех»</span>
          </div>
        )}

        {selected.length > 0 && (
          <div className="pa-cyber-board" role="region" aria-label="Матрица сравнения">
            <table className="pa-cyber-table">
              <thead>
                <tr>
                  <th className="pa-cyber-corner">
                    <span>SECTION</span>
                    <span className="pa-cyber-corner-sub">вкладка</span>
                  </th>
                  {selected.map((m) => (
                    <th key={m.userId} title={`${memberName(m)} · ${m.roleLabel}`}>
                      <span className="pa-cyber-col-name">{shortName(m)}</span>
                      <span className="pa-cyber-col-role">{m.roleLabel}</span>
                      <span className="pa-cyber-col-bar" aria-hidden="true">
                        <i style={{
                          width: `${Math.round(((m.effectiveSections || []).length / Math.max(1, configurableSections.length)) * 100)}%`,
                        }}
                        />
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {matrixRows.map((row) => (
                  <tr
                    key={row.sectionId}
                    className={`pa-cyber-row${row.hasDiff ? ' is-diff' : ''}${row.openCount === selected.length ? ' is-full' : ''}${row.openCount === 0 ? ' is-none' : ''}`}
                  >
                    <th scope="row">
                      <span className="pa-cyber-sec-group">{row.group}</span>
                      <span className="pa-cyber-sec-label">{row.label}</span>
                    </th>
                    {row.cells.map((c) => (
                      <td key={c.userId}>
                        <span
                          className={`pa-cyber-cell${c.open ? ' is-open' : ' is-closed'}${c.override === true ? ' is-grant' : ''}${c.override === false ? ' is-deny' : ''}`}
                          title={
                            c.open
                              ? (c.override === true ? 'Открыто (персонально выдано)' : 'Открыто')
                              : (c.override === false ? 'Закрыто (персональный запрет)' : 'Закрыто')
                          }
                        >
                          <span className="pa-cyber-dot" aria-hidden="true" />
                          <span className="pa-cyber-cell-txt">{c.open ? 'ON' : 'OFF'}</span>
                        </span>
                      </td>
                    ))}
                  </tr>
                ))}
                {matrixRows.length === 0 && (
                  <tr>
                    <td colSpan={selected.length + 1} className="pa-cyber-none">
                      {onlyDiff ? 'Отличий нет — доступы совпадают' : 'Нет строк'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {selected.length > 0 && (
          <footer className="pa-cyber-legend">
            <span><i className="pa-cyber-lg pa-cyber-lg-on" /> открыто</span>
            <span><i className="pa-cyber-lg pa-cyber-lg-off" /> закрыто</span>
            <span><i className="pa-cyber-lg pa-cyber-lg-diff" /> есть отличия в строке</span>
            <span>угол ячейки · персональный override</span>
            {selected.length >= 2 && (
              <span className="pa-cyber-legend-stat">
                совпадений: {configurableSections.length - diffCount}/{configurableSections.length}
              </span>
            )}
          </footer>
        )}
      </div>
    </div>
  )
}

export default function PanelAccessSection() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busyKey, setBusyKey] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [roleTab, setRoleTab] = useState('senior_admin')
  const [viewTab, setViewTab] = useState('defaults')
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')
  const [helpOpen, setHelpOpen] = useState(false)

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
      if (d.roles?.length && !d.roles.some((r) => r.id === roleTab)) {
        setRoleTab(d.roles[0].id)
      }
    } catch (e) {
      setError(e?.message || 'Не удалось загрузить доступы')
      setData(null)
    } finally {
      setLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
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
      setData((prev) => {
        if (!prev) return prev
        return {
          ...prev,
          roleDefaults: {
            ...prev.roleDefaults,
            [roleTab]: {
              ...(prev.roleDefaults?.[roleTab] || {}),
              [sectionId]: enabled,
            },
          },
          members: (prev.members || []).map((m) => {
            if (m.role !== roleTab) return m
            if (m.overrides && Object.prototype.hasOwnProperty.call(m.overrides, sectionId)) return m
            const set = new Set(m.effectiveSections || [])
            if (enabled) set.add(sectionId)
            else set.delete(sectionId)
            return { ...m, effectiveSections: [...set] }
          }),
        }
      })
    } catch (e) {
      alert(e?.message || 'Ошибка')
      await load()
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

  const resetAllOverrides = async () => {
    if (!selected) return
    const overs = Object.keys(selected.overrides || {})
    if (!overs.length) {
      alert('Персональных исключений нет')
      return
    }
    if (!confirm('Сбросить все персональные исключения к дефолту роли?')) return
    setBusyKey(`user-${selected.userId}-reset`)
    try {
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
  }

  return (
    <section className="panel-security panel-panel-access">
      <header className="sec-header pa-header">
        <div className="pa-header-text">
          <h2 className="sec-title">Админ панель</h2>
          <p className="sec-subtitle">
            Дефолтные вкладки по ролям и персональный доступ каждого администратора.
            Только владелец · изменения применяются сразу.
          </p>
        </div>
        <button
          type="button"
          className="pa-help-btn"
          onClick={() => setHelpOpen(true)}
          title="Описание вкладки"
          aria-label="Описание вкладки"
        >
          <span className="pa-help-btn-icon" aria-hidden="true">?</span>
          <span className="pa-help-btn-text">Справка</span>
        </button>
      </header>

      <nav className="sec-tabs pa-view-tabs" aria-label="Разделы доступов">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`sec-tab${viewTab === t.id ? ' sec-tab-active' : ''}`}
            onClick={() => setViewTab(t.id)}
          >
            {t.label}
          </button>
        ))}
        <button
          type="button"
          className="sec-btn sec-btn-ghost sec-btn-sm pa-refresh"
          onClick={load}
          disabled={loading}
        >
          {loading ? '…' : 'Обновить'}
        </button>
      </nav>

      <div className="sec-tab-body pa-tab-body">
        {loading && !data && <p className="sec-loading">Загрузка матрицы доступов…</p>}
        {error && (
          <div className="pa-error elite-block">
            <p className="sec-empty" style={{ margin: 0 }}>{error}</p>
            <button type="button" className="sec-btn sec-btn-sm" onClick={load}>
              Повторить
            </button>
          </div>
        )}

        {data && viewTab === 'defaults' && (
          <div className="pa-pane pa-pane-defaults">
            <div className="pa-role-tabs" role="tablist" aria-label="Роли">
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
            <p className="pa-hint">
              Базовый набор вкладок при выдаче роли. Персональные исключения во вкладке «Администраторы».
            </p>
            <div className="pa-section-groups">
              {sectionsByGroup.map((g) => (
                <div key={g.id} className="pa-group elite-block">
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
          </div>
        )}

        {data && viewTab === 'members' && (
          <div className="pa-pane pa-pane-members">
            <div className="pa-people-toolbar">
              <label className="pa-member-select-wrap">
                <span className="pa-field-label">Администратор</span>
                <select
                  className="sec-input pa-member-select"
                  value={selectedId ?? ''}
                  onChange={(e) => setSelectedId(Number(e.target.value) || null)}
                >
                  {!members.length && <option value="">Нет сотрудников</option>}
                  {members.map((m) => (
                    <option key={m.userId} value={m.userId}>
                      {memberName(m)} · {m.roleLabel}
                    </option>
                  ))}
                </select>
              </label>
              <label className="pa-search-wrap">
                <span className="pa-field-label">Поиск</span>
                <input
                  className="sec-input pa-search"
                  placeholder="Имя, @username, ID…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </label>
            </div>

            <div className="pa-people-split">
              <ul className="pa-member-list" aria-label="Список администраторов">
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
                        <h3 className="pa-detail-name">{memberName(selected)}</h3>
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
                        onClick={resetAllOverrides}
                      >
                        Сбросить исключения
                      </button>
                    </div>

                    <div className="pa-section-groups">
                      {sectionsByGroup.map((g) => (
                        <div key={g.id} className="pa-group elite-block">
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
                                  <div className="pa-user-actions" role="group" aria-label={`Доступ: ${s.label}`}>
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
                                    <span className={`pa-eff${on ? ' is-on' : ''}`}>
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
        )}

        {data && viewTab === 'compare' && (
          <ComparePane
            allMembers={data.members || []}
            sectionsByGroup={sectionsByGroup}
            configurableSections={configurableSections}
          />
        )}
      </div>

      {helpOpen && <HelpModal onClose={() => setHelpOpen(false)} />}
    </section>
  )
}
