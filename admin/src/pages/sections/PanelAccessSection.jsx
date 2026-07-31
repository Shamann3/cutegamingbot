import { memo, startTransition, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  fetchPanelAccess,
  setPanelRoleDefault,
  setPanelUserAccess,
  setPanelUserAccessBatch,
} from '../../lib/adminClient'
import { sectionBlurb } from '../../constants/panelNav'
import { parseAccessKey } from '../../constants/panelAccessTree'
import PanelAccessWizard from './PanelAccessWizard'

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
  { id: 'wizard', label: 'Простая настройка' },
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

function memberHasKey(m, key) {
  const { parentId, tabId } = parseAccessKey(key)
  if (!tabId) {
    return m._effSet ? m._effSet.has(parentId) : (m.effectiveSections || []).includes(parentId)
  }
  const parentOn = m._effSet
    ? m._effSet.has(parentId)
    : (m.effectiveSections || []).includes(parentId)
  if (!parentOn) return false
  return (m.effectiveTabs?.[parentId] || []).includes(tabId)
}

function applyKeyToMember(m, key, open, roleMap) {
  const overrides = { ...(m.overrides || {}) }
  overrides[key] = !!open
  const { parentId, tabId } = parseAccessKey(key)
  const set = new Set(m.effectiveSections || [])
  const tabs = { ...(m.effectiveTabs || {}) }

  if (!tabId) {
    if (open) set.add(parentId)
    else set.delete(parentId)
  } else {
    const resolved = Object.prototype.hasOwnProperty.call(overrides, key)
      ? !!overrides[key]
      : !!roleMap?.[key]
    const list = new Set(tabs[parentId] || [])
    if (resolved) list.add(tabId)
    else list.delete(tabId)
    tabs[parentId] = [...list]
  }

  return {
    ...m,
    overrides,
    effectiveSections: [...set],
    _effSet: set,
    effectiveTabs: tabs,
  }
}

function resetKeyOnMember(m, key, roleMap) {
  const overrides = { ...(m.overrides || {}) }
  delete overrides[key]
  const { parentId, tabId } = parseAccessKey(key)
  const fromRole = !!roleMap?.[key]
  const set = new Set(m.effectiveSections || [])
  const tabs = { ...(m.effectiveTabs || {}) }

  if (!tabId) {
    if (fromRole) set.add(parentId)
    else set.delete(parentId)
  } else {
    const list = new Set(tabs[parentId] || [])
    if (fromRole) list.add(tabId)
    else list.delete(tabId)
    tabs[parentId] = [...list]
  }

  return {
    ...m,
    overrides,
    effectiveSections: [...set],
    _effSet: set,
    effectiveTabs: tabs,
  }
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

function ExpandBtn({ open, onClick, label }) {
  return (
    <button
      type="button"
      className={`pa-expand-btn${open ? ' is-open' : ''}`}
      onClick={onClick}
      aria-expanded={open}
      title={open ? 'Свернуть вкладки' : 'Показать внутренние вкладки'}
      aria-label={label}
    >
      <span aria-hidden="true">{open ? '▾' : '▸'}</span>
    </button>
  )
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
          «Админ панель» — центр управления видимостью разделов и внутренних вкладок.
          Доступна только владельцу. Изменения применяются сразу.
        </p>

        <ul className="pa-help-list">
          <li>
            <strong>Простая настройка</strong>
            <span>
              Выберите администратора и пройдите по разделам как по слайдам:
              разрешить / запретить раздел и каждую внутреннюю вкладку.
            </span>
          </li>
          <li>
            <strong>Дефолты ролей</strong>
            <span>
              Базовый набор для старшего, младшего и модератора.
              Раскройте раздел (▸), чтобы настроить внутренние вкладки.
            </span>
          </li>
          <li>
            <strong>Администраторы</strong>
            <span>
              Персональные исключения: Выдать / Дефолт / Запрет
              для раздела и каждой внутренней вкладки.
            </span>
          </li>
          <li>
            <strong>Сравнение</strong>
            <span>
              Матрица: клик ON/OFF, Shift+клик — сброс к дефолту.
              Раскройте строку раздела, чтобы сравнить внутренние вкладки.
            </span>
          </li>
        </ul>

        <p className="pa-help-note">
          Итоговый доступ = дефолт роли ± персональные исключения.
          Можно открыть «Стафф», но скрыть, например, «Зарплаты».
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

const ComparePane = memo(function ComparePane({
  allMembers,
  treeByGroup,
  flatKeys,
  expanded,
  onToggleExpand,
  busyKeys,
  onToggleCell,
  onResetCell,
  onSetRowForAll,
}) {
  const [picked, setPicked] = useState(() => new Set())
  const [onlyDiff, setOnlyDiff] = useState(false)
  const [roleFilter, setRoleFilter] = useState('all')

  const pool = useMemo(() => {
    if (roleFilter === 'all') return allMembers
    return allMembers.filter((m) => m.role === roleFilter)
  }, [allMembers, roleFilter])

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
    for (const g of treeByGroup) {
      for (const node of g.items) {
        const pushRow = (accessKey, label, blurb, depth, parentId, childCount) => {
          const cells = selected.map((m) => ({
            userId: m.userId,
            name: memberName(m),
            open: memberHasKey(m, accessKey),
            override: m.overrides?.[accessKey],
          }))
          const opens = cells.map((c) => c.open)
          const hasDiff = opens.length > 1 && new Set(opens.map(Boolean)).size > 1
          rows.push({
            sectionId: accessKey,
            label,
            group: g.label,
            blurb,
            cells,
            hasDiff,
            openCount: opens.filter(Boolean).length,
            depth,
            parentId,
            childCount,
            expanded: expanded.has(parentId || accessKey),
          })
        }

        pushRow(
          node.id,
          node.label,
          node.blurb || sectionBlurb(node.id),
          0,
          null,
          node.children?.length || 0,
        )

        if (expanded.has(node.id) && node.children?.length) {
          for (const ch of node.children) {
            pushRow(ch.key, ch.label, ch.blurb || '', 1, node.id, 0)
          }
        }
      }
    }
    return onlyDiff ? rows.filter((r) => r.hasDiff) : rows
  }, [treeByGroup, selected, onlyDiff, expanded])

  const diffCount = useMemo(() => {
    if (selected.length < 2) return 0
    let n = 0
    for (const key of flatKeys) {
      const opens = selected.map((m) => memberHasKey(m, key))
      if (new Set(opens.map(Boolean)).size > 1) n += 1
    }
    return n
  }, [selected, flatKeys])

  const cellBusy = (userId, sectionId) => busyKeys?.has(`cmp-${userId}-${sectionId}`)
  const rowBusy = (sectionId) => busyKeys?.has(`cmp-row-${sectionId}`)

  return (
    <div className="pa-pane pa-pane-compare">
      <div className="pa-cyber">
        <header className="pa-cyber-head">
          <div>
            <p className="pa-cyber-kicker">ACCESS MATRIX // COMPARE</p>
            <h3 className="pa-cyber-title">Сравнение доступов</h3>
            <p className="pa-cyber-sub">
              Клик по ячейке — вкл/выкл. Shift+клик — сброс к дефолту роли.
              Раскройте раздел (▸), чтобы увидеть внутренние вкладки.
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
              <b>{flatKeys.length}</b>
              <em>ключей</em>
            </span>
          </div>
        </header>

        <div className="pa-cyber-controls">
          <div className="pa-cyber-filters">
            {[
              ['all', 'Все роли'],
              ['senior_admin', 'Старшие'],
              ['junior_admin', 'Младшие'],
              ['moderator', 'Модераторы'],
            ].map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={`pa-cyber-chip${roleFilter === id ? ' is-on' : ''}`}
                onClick={() => setRoleFilter(id)}
              >
                {label}
              </button>
            ))}
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
          {pool.length === 0 && <p className="pa-empty">Нет администраторов в этом фильтре</p>}
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
                    {m.roleLabel} · {n} разд.
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
                    <span className="pa-cyber-corner-sub">раздел · внутренние вкладки</span>
                  </th>
                  {selected.map((m) => (
                    <th key={m.userId} title={`${memberName(m)} · ${m.roleLabel}`}>
                      <span className="pa-cyber-col-name">{shortName(m)}</span>
                      <span className="pa-cyber-col-role">{m.roleLabel}</span>
                      <span className="pa-cyber-col-bar" aria-hidden="true">
                        <i style={{
                          width: `${Math.round(((m.effectiveSections || []).length / Math.max(1, flatKeys.filter((k) => !k.includes('.')).length)) * 100)}%`,
                        }}
                        />
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {matrixRows.map((row) => {
                  const rBusy = rowBusy(row.sectionId)
                  const isChild = row.depth > 0
                  return (
                    <tr
                      key={row.sectionId}
                      className={`pa-cyber-row${row.hasDiff ? ' is-diff' : ''}${row.openCount === selected.length ? ' is-full' : ''}${row.openCount === 0 ? ' is-none' : ''}${rBusy ? ' is-busy' : ''}${isChild ? ' is-child' : ''}`}
                    >
                      <th scope="row">
                        <div className={`pa-cyber-sec${isChild ? ' is-child' : ''}`}>
                          <span className="pa-cyber-sec-group">{isChild ? '↳ вкладка' : row.group}</span>
                          <div className="pa-cyber-sec-line">
                            {!isChild && row.childCount > 0 && (
                              <ExpandBtn
                                open={expanded.has(row.sectionId)}
                                onClick={() => onToggleExpand?.(row.sectionId)}
                                label={`Внутренние вкладки: ${row.label}`}
                              />
                            )}
                            <span className="pa-cyber-sec-label">{row.label}</span>
                          </div>
                          {row.blurb && !isChild && (
                            <p className="pa-cyber-sec-blurb">{row.blurb}</p>
                          )}
                          {selected.length > 1 && (
                            <div className="pa-cyber-row-ops">
                              <button
                                type="button"
                                className="pa-cyber-mini"
                                disabled={rBusy}
                                onClick={() => onSetRowForAll?.(row.sectionId, true, selected.map((m) => m.userId))}
                              >
                                всем ON
                              </button>
                              <button
                                type="button"
                                className="pa-cyber-mini"
                                disabled={rBusy}
                                onClick={() => onSetRowForAll?.(row.sectionId, false, selected.map((m) => m.userId))}
                              >
                                всем OFF
                              </button>
                            </div>
                          )}
                        </div>
                      </th>
                      {row.cells.map((c) => {
                        const busy = cellBusy(c.userId, row.sectionId) || rBusy
                        return (
                          <td key={c.userId}>
                            <button
                              type="button"
                              className={`pa-cyber-cell${c.open ? ' is-open' : ' is-closed'}${c.override === true ? ' is-grant' : ''}${c.override === false ? ' is-deny' : ''}${busy ? ' is-busy' : ''}`}
                              disabled={busy}
                              aria-pressed={c.open}
                              title={
                                c.open
                                  ? `${c.name}: открыто. Клик — закрыть. Shift+клик — дефолт.`
                                  : `${c.name}: закрыто. Клик — открыть. Shift+клик — дефолт.`
                              }
                              onClick={(e) => {
                                if (e.shiftKey) {
                                  onResetCell?.(c.userId, row.sectionId)
                                  return
                                }
                                onToggleCell?.(c.userId, row.sectionId, !c.open)
                              }}
                            >
                              <span className="pa-cyber-dot" aria-hidden="true" />
                              <span className="pa-cyber-cell-txt">{busy ? '…' : (c.open ? 'ON' : 'OFF')}</span>
                            </button>
                          </td>
                        )
                      })}
                    </tr>
                  )
                })}
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
            <span><i className="pa-cyber-lg pa-cyber-lg-on" /> открыто · клик выкл</span>
            <span><i className="pa-cyber-lg pa-cyber-lg-off" /> закрыто · клик вкл</span>
            <span><i className="pa-cyber-lg pa-cyber-lg-diff" /> отличия в строке</span>
            <span>▸ · внутренние вкладки</span>
            <span>Shift+клик · дефолт роли</span>
          </footer>
        )}
      </div>
    </div>
  )
})

export default function PanelAccessSection() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busyKeys, setBusyKeys] = useState(() => new Set())
  const [selectedId, setSelectedId] = useState(null)
  const [roleTab, setRoleTab] = useState('senior_admin')
  const [viewTab, setViewTab] = useState('wizard')
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')
  const [helpOpen, setHelpOpen] = useState(false)
  const [expanded, setExpanded] = useState(() => new Set(['staff']))
  const pendingSeq = useRef(new Map())

  const markBusy = useCallback((key) => {
    setBusyKeys((prev) => {
      if (prev.has(key)) return prev
      const next = new Set(prev)
      next.add(key)
      return next
    })
  }, [])

  const clearBusy = useCallback((key) => {
    setBusyKeys((prev) => {
      if (!prev.has(key)) return prev
      const next = new Set(prev)
      next.delete(key)
      return next
    })
  }, [])

  const toggleExpand = useCallback((id) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const load = useCallback(async ({ silent = false } = {}) => {
    if (!silent) {
      setLoading(true)
      setError('')
    }
    try {
      const d = await fetchPanelAccess()
      d.members = (d.members || []).map((m) => ({
        ...m,
        _effSet: new Set(m.effectiveSections || []),
        effectiveTabs: m.effectiveTabs || {},
      }))
      setData(d)
      setSelectedId((prev) => {
        if (prev && (d.members || []).some((m) => m.userId === prev)) return prev
        return d.members?.[0]?.userId ?? null
      })
      if (d.roles?.length && !d.roles.some((r) => r.id === roleTab)) {
        setRoleTab(d.roles[0].id)
      }
    } catch (e) {
      if (!silent) {
        setError(e?.message || 'Не удалось загрузить доступы')
        setData(null)
      } else {
        throw e
      }
    } finally {
      if (!silent) setLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => { load() }, [load])

  const treeByGroup = useMemo(() => {
    const tree = data?.tree || []
    const groups = []
    const seen = new Set()
    for (const node of tree) {
      if (seen.has(node.group)) continue
      seen.add(node.group)
      groups.push({
        id: node.group,
        label: GROUP_LABELS[node.group] || node.group,
        items: tree
          .filter((x) => x.group === node.group)
          .map((x) => ({
            ...x,
            blurb: sectionBlurb(x.id),
            children: (x.children || []).map((ch) => ({
              ...ch,
              blurb: ch.blurb || '',
            })),
          })),
      })
    }
    return groups
  }, [data])

  const flatKeys = useMemo(() => {
    const keys = []
    for (const g of treeByGroup) {
      for (const node of g.items) {
        keys.push(node.id)
        for (const ch of node.children || []) keys.push(ch.key)
      }
    }
    return keys
  }, [treeByGroup])

  const membersForCompare = useMemo(() => {
    return (data?.members || []).map((m) => (
      m._effSet ? m : { ...m, _effSet: new Set(m.effectiveSections || []) }
    ))
  }, [data])

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

  const toggleRoleDefault = async (accessKey, enabled) => {
    const key = `role-${roleTab}-${accessKey}`
    startTransition(() => {
      setData((prev) => {
        if (!prev) return prev
        const nextRoleMap = {
          ...(prev.roleDefaults?.[roleTab] || {}),
          [accessKey]: enabled,
        }
        return {
          ...prev,
          roleDefaults: {
            ...prev.roleDefaults,
            [roleTab]: nextRoleMap,
          },
          members: (prev.members || []).map((m) => {
            if (m.role !== roleTab) return m
            if (m.overrides && Object.prototype.hasOwnProperty.call(m.overrides, accessKey)) return m
            const { parentId, tabId } = parseAccessKey(accessKey)
            const set = new Set(m.effectiveSections || [])
            const tabs = { ...(m.effectiveTabs || {}) }
            if (!tabId) {
              if (enabled) set.add(parentId)
              else set.delete(parentId)
            } else {
              const list = new Set(tabs[parentId] || [])
              if (enabled) list.add(tabId)
              else list.delete(tabId)
              tabs[parentId] = [...list]
            }
            return {
              ...m,
              effectiveSections: [...set],
              _effSet: set,
              effectiveTabs: tabs,
            }
          }),
        }
      })
    })
    markBusy(key)
    try {
      await setPanelRoleDefault({ role: roleTab, sectionId: accessKey, enabled })
    } catch (e) {
      alert(e?.message || 'Ошибка')
      try { await load({ silent: true }) } catch { /* ignore */ }
    } finally {
      clearBusy(key)
    }
  }

  const patchMemberAccess = useCallback((userId, accessKey, mode) => {
    setData((prev) => {
      if (!prev) return prev
      let changed = false
      const membersNext = (prev.members || []).map((m) => {
        if (m.userId !== userId) return m
        changed = true
        const roleMap = prev.roleDefaults?.[m.role] || {}
        if (mode === 'reset') return resetKeyOnMember(m, accessKey, roleMap)
        return applyKeyToMember(m, accessKey, !!mode, roleMap)
      })
      if (!changed) return prev
      return { ...prev, members: membersNext }
    })
  }, [])

  const setUserSection = async (accessKey, mode) => {
    if (!selected) return
    const key = `user-${selected.userId}-${accessKey}`
    const patchMode = mode === 'default' ? 'reset' : mode === 'grant'
    startTransition(() => patchMemberAccess(selected.userId, accessKey, patchMode))
    markBusy(key)
    try {
      if (mode === 'default') {
        await setPanelUserAccess({ userId: selected.userId, sectionId: accessKey, reset: true })
      } else {
        await setPanelUserAccess({
          userId: selected.userId,
          sectionId: accessKey,
          allowed: mode === 'grant',
        })
      }
    } catch (e) {
      alert(e?.message || 'Ошибка')
      try { await load({ silent: true }) } catch { /* ignore */ }
    } finally {
      clearBusy(key)
    }
  }

  const wizardSetKey = useCallback(async (userId, accessKey, allowed) => {
    const key = `wiz-${userId}-${accessKey}`
    startTransition(() => patchMemberAccess(userId, accessKey, !!allowed))
    markBusy(key)
    try {
      await setPanelUserAccess({ userId, sectionId: accessKey, allowed: !!allowed })
    } catch (e) {
      alert(e?.message || 'Ошибка')
      try { await load({ silent: true }) } catch { /* ignore */ }
    } finally {
      clearBusy(key)
    }
  }, [patchMemberAccess, markBusy, clearBusy, load])

  const compareToggleCell = useCallback(async (userId, sectionId, nextOpen) => {
    const key = `cmp-${userId}-${sectionId}`
    const seq = (pendingSeq.current.get(key) || 0) + 1
    pendingSeq.current.set(key, seq)
    startTransition(() => patchMemberAccess(userId, sectionId, nextOpen))
    markBusy(key)
    try {
      await setPanelUserAccess({ userId, sectionId, allowed: !!nextOpen })
    } catch (e) {
      if (pendingSeq.current.get(key) === seq) {
        alert(e?.message || 'Ошибка')
        try { await load({ silent: true }) } catch { /* ignore */ }
      }
    } finally {
      if (pendingSeq.current.get(key) === seq) {
        pendingSeq.current.delete(key)
        clearBusy(key)
      }
    }
  }, [patchMemberAccess, markBusy, clearBusy, load])

  const compareResetCell = useCallback(async (userId, sectionId) => {
    const key = `cmp-${userId}-${sectionId}`
    const seq = (pendingSeq.current.get(key) || 0) + 1
    pendingSeq.current.set(key, seq)
    startTransition(() => patchMemberAccess(userId, sectionId, 'reset'))
    markBusy(key)
    try {
      await setPanelUserAccess({ userId, sectionId, reset: true })
    } catch (e) {
      if (pendingSeq.current.get(key) === seq) {
        alert(e?.message || 'Ошибка')
        try { await load({ silent: true }) } catch { /* ignore */ }
      }
    } finally {
      if (pendingSeq.current.get(key) === seq) {
        pendingSeq.current.delete(key)
        clearBusy(key)
      }
    }
  }, [patchMemberAccess, markBusy, clearBusy, load])

  const compareSetRowForAll = useCallback(async (sectionId, open, userIds) => {
    const ids = userIds || []
    if (!ids.length) return
    const key = `cmp-row-${sectionId}`
    const idSet = new Set(ids)
    startTransition(() => {
      setData((prev) => {
        if (!prev) return prev
        return {
          ...prev,
          members: (prev.members || []).map((m) => {
            if (!idSet.has(m.userId)) return m
            const roleMap = prev.roleDefaults?.[m.role] || {}
            return applyKeyToMember(m, sectionId, !!open, roleMap)
          }),
        }
      })
    })
    markBusy(key)
    try {
      await setPanelUserAccessBatch(
        ids.map((uid) => ({ userId: uid, sectionId, allowed: !!open })),
      )
    } catch (e) {
      alert(e?.message || 'Ошибка')
      try { await load({ silent: true }) } catch { /* ignore */ }
    } finally {
      clearBusy(key)
    }
  }, [markBusy, clearBusy, load])

  const sectionState = (accessKey) => {
    if (!selected) return { on: false, state: 'default' }
    const ov = selected.overrides?.[accessKey]
    if (ov === true) return { on: true, state: 'grant' }
    if (ov === false) return { on: false, state: 'deny' }
    return { on: memberHasKey(selected, accessKey), state: 'default' }
  }

  const resetAllOverrides = async () => {
    if (!selected) return
    const overs = Object.keys(selected.overrides || {})
    if (!overs.length) {
      alert('Персональных исключений нет')
      return
    }
    if (!confirm('Сбросить все персональные исключения к дефолту роли?')) return
    const key = `user-${selected.userId}-reset`
    markBusy(key)
    startTransition(() => {
      for (const accessKey of overs) patchMemberAccess(selected.userId, accessKey, 'reset')
    })
    try {
      await setPanelUserAccessBatch(
        overs.map((sectionId) => ({
          userId: selected.userId,
          sectionId,
          reset: true,
        })),
      )
    } catch (e) {
      alert(e?.message || 'Ошибка')
      try { await load({ silent: true }) } catch { /* ignore */ }
    } finally {
      clearBusy(key)
    }
  }

  const renderDefaultsNode = (node) => {
    const on = !!roleDefaults[node.id]
    const busy = busyKeys.has(`role-${roleTab}-${node.id}`)
    const open = expanded.has(node.id)
    const kids = node.children || []
    return (
      <li key={node.id} className="pa-tree-block">
        <div className="pa-section-row pa-section-row-parent">
          <div className="pa-section-who">
            {kids.length > 0 && (
              <ExpandBtn
                open={open}
                onClick={() => toggleExpand(node.id)}
                label={`Внутренние вкладки: ${node.label}`}
              />
            )}
            <span className="pa-section-name">{node.label}</span>
            {kids.length > 0 && (
              <span className="pa-child-count">{kids.length} вкл.</span>
            )}
          </div>
          <Toggle
            on={on}
            disabled={busy}
            label={`${node.label}: ${on ? 'включено' : 'выключено'}`}
            onClick={() => toggleRoleDefault(node.id, !on)}
          />
        </div>
        {open && kids.length > 0 && (
          <ul className="pa-child-list">
            {kids.map((ch) => {
              const chOn = !!roleDefaults[ch.key]
              const chBusy = busyKeys.has(`role-${roleTab}-${ch.key}`)
              return (
                <li key={ch.key} className="pa-section-row pa-section-row-child">
                  <span className="pa-section-name">
                    <span className="pa-child-mark" aria-hidden="true">↳</span>
                    {ch.label}
                  </span>
                  <Toggle
                    on={chOn}
                    disabled={chBusy}
                    label={`${ch.label}: ${chOn ? 'включено' : 'выключено'}`}
                    onClick={() => toggleRoleDefault(ch.key, !chOn)}
                  />
                </li>
              )
            })}
          </ul>
        )}
      </li>
    )
  }

  const renderMemberNode = (node) => {
    const { on, state } = sectionState(node.id)
    const busy = busyKeys.has(`user-${selected.userId}-${node.id}`)
    const open = expanded.has(node.id)
    const kids = node.children || []
    return (
      <li key={node.id} className="pa-tree-block">
        <div className="pa-section-row pa-section-row-user pa-section-row-parent">
          <div className="pa-section-who">
            {kids.length > 0 && (
              <ExpandBtn
                open={open}
                onClick={() => toggleExpand(node.id)}
                label={`Внутренние вкладки: ${node.label}`}
              />
            )}
            <span className="pa-section-name">{node.label}</span>
            <StateChip state={state} />
          </div>
          <div className="pa-user-actions" role="group" aria-label={`Доступ: ${node.label}`}>
            <button type="button" className={`pa-pill${state === 'grant' ? ' is-on' : ''}`} disabled={busy} onClick={() => setUserSection(node.id, 'grant')}>Выдать</button>
            <button type="button" className={`pa-pill${state === 'default' ? ' is-on' : ''}`} disabled={busy} onClick={() => setUserSection(node.id, 'default')}>Дефолт</button>
            <button type="button" className={`pa-pill pa-pill-danger${state === 'deny' ? ' is-on' : ''}`} disabled={busy} onClick={() => setUserSection(node.id, 'deny')}>Запрет</button>
            <span className={`pa-eff${on ? ' is-on' : ''}`}>{on ? 'открыто' : 'закрыто'}</span>
          </div>
        </div>
        {open && kids.length > 0 && (
          <ul className={`pa-child-list${!on ? ' is-dim' : ''}`}>
            {kids.map((ch) => {
              const st = sectionState(ch.key)
              const chBusy = busyKeys.has(`user-${selected.userId}-${ch.key}`)
              return (
                <li key={ch.key} className="pa-section-row pa-section-row-user pa-section-row-child">
                  <div className="pa-section-who">
                    <span className="pa-section-name">
                      <span className="pa-child-mark" aria-hidden="true">↳</span>
                      {ch.label}
                    </span>
                    <StateChip state={st.state} />
                  </div>
                  <div className="pa-user-actions" role="group" aria-label={`Доступ: ${ch.label}`}>
                    <button type="button" className={`pa-pill${st.state === 'grant' ? ' is-on' : ''}`} disabled={chBusy} onClick={() => setUserSection(ch.key, 'grant')}>Выдать</button>
                    <button type="button" className={`pa-pill${st.state === 'default' ? ' is-on' : ''}`} disabled={chBusy} onClick={() => setUserSection(ch.key, 'default')}>Дефолт</button>
                    <button type="button" className={`pa-pill pa-pill-danger${st.state === 'deny' ? ' is-on' : ''}`} disabled={chBusy} onClick={() => setUserSection(ch.key, 'deny')}>Запрет</button>
                    <span className={`pa-eff${st.on && on ? ' is-on' : ''}`}>
                      {st.on && on ? 'открыто' : 'закрыто'}
                    </span>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </li>
    )
  }

  return (
    <section className="panel-security panel-panel-access">
      <header className="sec-header pa-header">
        <div className="pa-header-text">
          <h2 className="sec-title">Админ панель</h2>
          <p className="sec-subtitle">
            Разделы и внутренние вкладки для каждой роли и каждого администратора.
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

        {data && viewTab === 'wizard' && (
          <PanelAccessWizard
            members={data.members || []}
            roleDefaults={data.roleDefaults || {}}
            busyKeys={busyKeys}
            onSetKey={wizardSetKey}
          />
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
              Базовый набор при выдаче роли. Нажмите ▸ у раздела, чтобы настроить внутренние вкладки
              (например Стафф → Зарплаты).
            </p>
            <div className="pa-section-groups">
              {treeByGroup.map((g) => (
                <div key={g.id} className="pa-group elite-block">
                  <p className="pa-group-label">{g.label}</p>
                  <ul className="pa-section-list">
                    {g.items.map(renderDefaultsNode)}
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
                        {(m.effectiveSections || []).length} разд.
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
                        disabled={[...busyKeys].some((k) => k.startsWith(`user-${selected.userId}`))}
                        onClick={resetAllOverrides}
                      >
                        Сбросить исключения
                      </button>
                    </div>

                    <div className="pa-section-groups">
                      {treeByGroup.map((g) => (
                        <div key={g.id} className="pa-group elite-block">
                          <p className="pa-group-label">{g.label}</p>
                          <ul className="pa-section-list">
                            {g.items.map(renderMemberNode)}
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
            allMembers={membersForCompare}
            treeByGroup={treeByGroup}
            flatKeys={flatKeys}
            expanded={expanded}
            onToggleExpand={toggleExpand}
            busyKeys={busyKeys}
            onToggleCell={compareToggleCell}
            onResetCell={compareResetCell}
            onSetRowForAll={compareSetRowForAll}
          />
        )}
      </div>

      {helpOpen && <HelpModal onClose={() => setHelpOpen(false)} />}
    </section>
  )
}
