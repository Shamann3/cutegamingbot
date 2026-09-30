import { useCallback, useEffect, useState } from 'react'
import { fetchStaffPunishRights, saveStaffPunishRights } from '../lib/adminClient'
import { STAFF_PUNISH_LABELS } from '../lib/panelPreview'
import RightSwitch from './RightSwitch'

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

export default function StaffPunishRole({ role }) {
  const [columns, setColumns] = useState([])
  const [roles, setRoles] = useState([])
  const [pick, setPick] = useState(role || '')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchStaffPunishRights()
      setColumns(data.columns || [])
      setRoles(data.roles || [])
    } catch (err) {
      setError(err?.message || 'Наказания должностей не открылись')
      setColumns([])
      setRoles([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (role) setPick(role)
  }, [role])

  const row = roles.find((item) => item.role === pick) || null
  const linked = Boolean(role && row && row.role === role)

  const toggle = async (col, next) => {
    if (!row) return
    const key = `${row.role}:${col}`
    setBusy(key)
    setError('')
    setNotice('')
    const prev = roles
    const permissions = { ...(row.permissions || {}), [col]: next }
    setRoles((list) => list.map((item) => (
      item.role === row.role ? { ...item, permissions } : item
    )))
    try {
      await saveStaffPunishRights(row.role, permissions)
      setNotice(`Наказания «${row.title || row.role}» сохранены. Панель и бот читают эту строку.`)
    } catch (err) {
      setRoles(prev)
      setError(err?.message || 'Наказание не сохранилось')
    } finally {
      setBusy('')
    }
  }

  return (
    <section className="staff-punish-role">
      <h3 className="realm-h">Наказания этой должности</h3>
      <p className="staff-hint">
        {linked
          ? 'Выключенное действие нельзя обойти ни в панели, ни в боте.'
          : 'Строка staff_rules называется иначе, чем роль панели. Выберите должность, чьи наказания меняете.'}
      </p>
      {error && <p className="realm-alert" role="alert">{error}</p>}
      {notice && <p className="realm-note" role="status">{notice}</p>}
      {loading && <p className="sec-loading">Сверяем наказания…</p>}
      {!loading && roles.length > 1 && (
        <nav className="sec-tabs" aria-label="Должности staff_rules">
          {roles.map((item) => (
            <button
              key={item.role}
              type="button"
              className={`sec-tab${pick === item.role ? ' sec-tab-active' : ''}`}
              onClick={() => setPick(item.role)}
            >
              {item.title || item.role}
            </button>
          ))}
        </nav>
      )}
      {!loading && row && (
        <div className="staff-switch-list">
          {columns.map((col) => (
            <RightSwitch
              key={col}
              title={STAFF_PUNISH_LABELS[col] || col}
              hint={COL_HINTS[col] || ''}
              on={!!row.permissions?.[col]}
              disabled={busy === `${row.role}:${col}` || !!row.locked}
              onChange={(next) => toggle(col, next)}
            />
          ))}
        </div>
      )}
      {!loading && !row && !error && (
        <p className="sec-empty">В staff_rules нет должностей.</p>
      )}
    </section>
  )
}
