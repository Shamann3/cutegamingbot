import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchStaffPunishRights, saveStaffPunishRights } from '../lib/adminClient'
import { STAFF_PUNISH_LABELS } from '../lib/panelPreview'
import { showToast } from './ToastHost'

const COL_HINTS = {
  mute: 'Заткнуть в одном чате',
  muteall: 'Заткнуть во всех официальных группах',
  unmute: 'Снять молчание в чате',
  kick: 'Убрать из чата',
  kickall: 'Убрать из всех официальных групп',
  warn: 'Предупреждение в одном чате',
  warnall: 'Предупреждение во всех официальных группах',
  warnfull: 'Предупреждение на весь проект',
  ban: 'Бан в одном чате',
  banall: 'Бан во всех официальных группах',
  banfull: 'Запрет на весь проект',
}

const FAMILIES = [
  ['mute', 'muteall', 'unmute'],
  ['kick', 'kickall'],
  ['warn', 'warnall', 'warnfull'],
  ['ban', 'banall', 'banfull'],
]

const SKELETON_ROWS = 4
// Тост висит ~3.2 с: пока он на экране, повторное «Сохранено» для той же должности не нужно.
const SAVED_TOAST_GAP_MS = 3000

function groupColumns(columns) {
  const known = new Set(FAMILIES.flat())
  const families = FAMILIES.map((family) => family.filter((col) => columns.includes(col)))
  const rest = columns.filter((col) => !known.has(col))
  return [...families, rest].filter((group) => group.length > 0)
}

function PunishSwitch({ title, hint, on, disabled, onChange }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      disabled={disabled}
      className={`staff-punish-switch${on ? ' is-on' : ''}`}
      onClick={() => onChange(!on)}
    >
      <span className="staff-punish-copy">
        <strong>{title}</strong>
        {hint ? <em>{hint}</em> : null}
      </span>
      <span className={`pa-toggle${on ? ' is-on' : ''}`} aria-hidden="true">
        <span className="pa-toggle-track"><span className="pa-toggle-knob" /></span>
        <span className="pa-toggle-label">{on ? 'Вкл' : 'Выкл'}</span>
      </span>
    </button>
  )
}

export default function StaffPunishRole({ role }) {
  const [columns, setColumns] = useState([])
  const [roles, setRoles] = useState([])
  const [problem, setProblem] = useState('')
  const [pick, setPick] = useState(role || '')
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [busy, setBusy] = useState(() => new Set())
  const request = useRef(0)
  const lastToast = useRef({ title: '', at: 0 })

  const load = useCallback(async () => {
    const id = request.current + 1
    request.current = id
    setLoading(true)
    setLoadError('')
    try {
      const data = await fetchStaffPunishRights()
      if (request.current !== id) return
      setColumns(data?.columns || [])
      setRoles(data?.roles || [])
      setProblem(data?.problem || '')
    } catch (err) {
      if (request.current !== id) return
      setLoadError(err?.message || 'Наказания должностей не открылись')
      setColumns([])
      setRoles([])
      setProblem('')
    } finally {
      if (request.current === id) setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    return () => { request.current += 1 }
  }, [load])

  useEffect(() => {
    if (role) setPick(role)
  }, [role])

  const row = roles.find((item) => item.role === pick) || null
  const linked = Boolean(role && row && row.role === role)
  const missingRow = Boolean(role) && !roles.some((item) => item.role === role)
  const ready = !loading && !loadError && !problem

  const confirmSaved = (title) => {
    const now = Date.now()
    const last = lastToast.current
    if (last.title === title && now - last.at < SAVED_TOAST_GAP_MS) return
    lastToast.current = { title, at: now }
    showToast(`Сохранено для «${title}». Бот применит изменение в течение минуты.`)
  }

  const setFlag = (roleKey, col, on) => setRoles((list) => list.map((item) => (
    item.role === roleKey ? { ...item, permissions: { ...item.permissions, [col]: on } } : item
  )))

  const markBusy = (key, on) => setBusy((current) => {
    const next = new Set(current)
    if (on) next.add(key)
    else next.delete(key)
    return next
  })

  const toggle = async (col, next) => {
    if (!row) return
    const roleKey = row.role
    const title = row.title || roleKey
    const key = `${roleKey}:${col}`
    markBusy(key, true)
    setFlag(roleKey, col, next)
    try {
      const saved = await saveStaffPunishRights(roleKey, { [col]: next })
      const truth = saved?.role?.permissions
      if (truth && col in truth) setFlag(roleKey, col, Boolean(truth[col]))
      confirmSaved(title)
    } catch (err) {
      setFlag(roleKey, col, !next)
      showToast(err?.message || 'Наказание не сохранилось', 'error')
    } finally {
      markBusy(key, false)
    }
  }

  return (
    <section
      className="staff-punish-role elite-block"
      aria-labelledby="staff-punish-title"
      aria-busy={loading || undefined}
    >
      <header className="staff-punish-head">
        <h3 id="staff-punish-title" className="staff-punish-title">Наказания должности</h3>
        {ready && row && <span className="staff-punish-for">{row.title || row.role}</span>}
      </header>

      {loading && (
        <div className="staff-punish-skeleton" aria-hidden="true">
          {Array.from({ length: SKELETON_ROWS }, (_, index) => <span key={index} className="skeleton" />)}
        </div>
      )}

      {!loading && loadError && (
        <div className="staff-punish-state" role="alert">
          <p>{loadError}</p>
          <button type="button" className="sec-btn sec-btn-sm" onClick={load}>Повторить</button>
        </div>
      )}

      {!loading && !loadError && problem && (
        <div className="staff-punish-state">
          <p>{problem}</p>
          <button type="button" className="sec-btn sec-btn-ghost sec-btn-sm" onClick={load}>Проверить снова</button>
        </div>
      )}

      {ready && roles.length === 0 && (
        <p className="staff-punish-lead">В staff_rules пока нет ни одной должности.</p>
      )}

      {ready && roles.length > 0 && (
        <>
          <p className="staff-punish-lead">
            {linked && 'Выключенное действие нельзя обойти ни в панели, ни в боте.'}
            {!linked && missingRow && 'У этой должности нет строки в staff_rules, поэтому бот не даёт ей наказывать. Выберите строку, которую хотите настроить.'}
            {!linked && !missingRow && 'Выберите строку staff_rules, чьи наказания меняете.'}
          </p>
          {!linked && (
            <nav className="sec-tabs staff-punish-rows" aria-label="Строки staff_rules">
              {roles.map((item) => (
                <button
                  key={item.role}
                  type="button"
                  className={`sec-tab${pick === item.role ? ' sec-tab-active' : ''}`}
                  aria-pressed={pick === item.role}
                  onClick={() => setPick(item.role)}
                >
                  {item.title || item.role}
                </button>
              ))}
            </nav>
          )}
          {row && (
            <div className="staff-punish-groups">
              {groupColumns(columns).map((group) => (
                <ul key={group[0]} className="staff-punish-group">
                  {group.map((col) => (
                    <li key={col}>
                      <PunishSwitch
                        title={STAFF_PUNISH_LABELS[col] || col}
                        hint={COL_HINTS[col] || ''}
                        on={!!row.permissions?.[col]}
                        disabled={busy.has(`${row.role}:${col}`) || !!row.locked}
                        onChange={(next) => toggle(col, next)}
                      />
                    </li>
                  ))}
                </ul>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  )
}
