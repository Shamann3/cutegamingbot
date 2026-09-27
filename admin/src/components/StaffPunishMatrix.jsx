import { useCallback, useEffect, useState } from 'react'
import { fetchStaffPunishRights, saveStaffPunishRights } from '../lib/adminClient'

const COL_LABELS = {
  mute: 'Мут',
  muteall: 'Муталл',
  unmute: 'Размут',
  kick: 'Кик',
  kickall: 'Кикалл',
  warn: 'Варн',
  warnall: 'Варналл',
  warnfull: 'Варнфулл',
  ban: 'Бан',
  banall: 'Баналл',
  banfull: 'Банфулл',
}

function levelLabel(importance) {
  if (importance == null) return ''
  return ` · ур. ${importance}`
}

/**
 * Матрица наказаний staff_rules: Владелец (5) … Кандидат/Отстранён.
 * Только создатель/владелец панели — через родителя.
 */
export default function StaffPunishMatrix() {
  const [columns, setColumns] = useState([])
  const [roles, setRoles] = useState([])
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
      setError(err?.message || 'Не удалось загрузить матрицу наказаний')
      setColumns([])
      setRoles([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const toggle = async (roleKey, col, next) => {
    const key = `${roleKey}:${col}`
    setBusy(key)
    setError('')
    setNotice('')
    const prev = roles
    setRoles((list) => list.map((r) => (
      r.role === roleKey
        ? { ...r, permissions: { ...r.permissions, [col]: next } }
        : r
    )))
    try {
      const row = prev.find((r) => r.role === roleKey)
      const permissions = { ...(row?.permissions || {}), [col]: next }
      await saveStaffPunishRights(roleKey, permissions)
      setNotice(`Сохранено: ${row?.title || roleKey}`)
    } catch (err) {
      setRoles(prev)
      setError(err?.message || 'Не удалось сохранить')
    } finally {
      setBusy('')
    }
  }

  return (
    <div className="spm-root">
      <header className="spm-head">
        <h3 className="spm-title">Наказания по должностям</h3>
        <p className="spm-lead">
          Иерархия из staff_rules (Владелец · 5 … Кандидат / Отстранён). Без включённого права действие
          в панели и боте недоступно — обойти нельзя.
        </p>
      </header>
      {error && <p className="realm-alert" role="alert">{error}</p>}
      {notice && <p className="realm-note" role="status">{notice}</p>}
      {loading && <p className="sec-loading">Загрузка матрицы…</p>}
      {!loading && roles.length === 0 && !error && (
        <p className="sec-empty">Таблица staff_rules пуста или недоступна.</p>
      )}
      {!loading && roles.length > 0 && (
        <div className="spm-scroll">
          <table className="spm-table">
            <thead>
              <tr>
                <th scope="col">Должность</th>
                {columns.map((col) => (
                  <th key={col} scope="col" title={col}>{COL_LABELS[col] || col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {roles.map((row) => (
                <tr key={row.role}>
                  <th scope="row">
                    <span className="spm-role-name">{row.title || row.role}</span>
                    <span className="spm-role-meta">{levelLabel(row.importance)}</span>
                  </th>
                  {columns.map((col) => {
                    const on = !!row.permissions?.[col]
                    const key = `${row.role}:${col}`
                    return (
                      <td key={col}>
                        <button
                          type="button"
                          className={`spm-cell${on ? ' is-on' : ''}`}
                          disabled={busy === key || !!row.locked}
                          aria-pressed={on}
                          title={on ? 'Разрешено — нажмите чтобы запретить' : 'Запрещено — нажмите чтобы разрешить'}
                          onClick={() => toggle(row.role, col, !on)}
                        >
                          {busy === key ? '…' : on ? '✓' : '—'}
                        </button>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <button type="button" className="sec-btn sec-btn-ghost sec-btn-sm" onClick={load} disabled={loading}>
        Обновить
      </button>
    </div>
  )
}
