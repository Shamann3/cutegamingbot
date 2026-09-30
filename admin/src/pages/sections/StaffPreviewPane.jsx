import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchPanelAccess, fetchStaffPunishRights } from '../../lib/adminClient'
import {
  STAFF_PUNISH_LABELS,
  ruCount,
  staffMemberPreview,
  staffPreviewNav,
  staffRolePreview,
} from '../../lib/panelPreview'

const MODES = [
  { id: 'role', label: 'Должность' },
  { id: 'person', label: 'Сотрудник' },
]

function punishLine(list) {
  if (list == null) return 'Наказания не сверились'
  const names = list.filter((key) => STAFF_PUNISH_LABELS[key]).map((key) => STAFF_PUNISH_LABELS[key])
  return names.length ? `Наказания: ${names.join(', ')}` : 'Наказаний нет'
}

function SectionChips({ nav }) {
  if (!nav.length) return <p className="preview-card-line">Ни одного раздела — панель откроется пустой.</p>
  return (
    <ul className="preview-chips" aria-label="Разделы меню">
      {nav.map((item) => <li key={item.id}>{item.labelRu || item.label}</li>)}
    </ul>
  )
}

export default function StaffPreviewPane({ onOpen }) {
  const [mode, setMode] = useState('role')
  const [data, setData] = useState(null)
  const [punish, setPunish] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [access, rules] = await Promise.all([
        fetchPanelAccess(),
        fetchStaffPunishRights().catch(() => null),
      ])
      setData(access)
      setPunish(Array.isArray(rules?.roles) ? rules.roles : null)
    } catch (err) {
      setError(err?.message || 'Должности и сотрудники не открылись')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const roles = useMemo(() => (data?.roles || []).map((role) => {
    const preview = staffRolePreview(data, role.id, punish)
    return { id: role.id, preview, nav: staffPreviewNav(preview) }
  }), [data, punish])

  const people = useMemo(() => {
    const needle = query.trim().toLowerCase().replace(/^@/, '')
    return (data?.members || [])
      .filter((member) => !needle
        || String(member.userId).includes(needle)
        || String(member.firstName || '').toLowerCase().includes(needle)
        || String(member.username || '').toLowerCase().includes(needle))
      .map((member) => {
        const preview = staffMemberPreview(member, punish)
        return { member, preview, nav: staffPreviewNav(preview) }
      })
  }, [data, punish, query])

  const total = data?.members?.length || 0

  return (
    <div className="preview-desk">
      <p className="staff-hint">
        Копия открывает панель Эпсилона так, как её видит должность или конкретный сотрудник:
        то же меню, те же вкладки, права и наказания. Это тестовый режим — смотреть можно всё,
        а изменения не сохраняются. Личные страницы вроде «Моей зарплаты» открываются от вашей учётной записи.
      </p>

      <div className="preview-toolbar">
        <nav className="sec-tabs" aria-label="Чью копию открыть">
          {MODES.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`sec-tab${mode === item.id ? ' sec-tab-active' : ''}`}
              aria-current={mode === item.id ? 'page' : undefined}
              onClick={() => setMode(item.id)}
            >
              {item.id === 'person' && total ? `${item.label} · ${total}` : item.label}
            </button>
          ))}
        </nav>
        <button type="button" className="sec-btn sec-btn-ghost sec-btn-sm" onClick={load} disabled={loading}>
          {loading ? 'Сверяем…' : 'Обновить'}
        </button>
      </div>

      {error && (
        <div className="staff-app-card" role="alert">
          <p className="staff-app-meta">{error}</p>
          <div className="staff-app-actions">
            <button type="button" className="sec-btn sec-btn-sm" onClick={load}>Повторить</button>
          </div>
        </div>
      )}
      {loading && !data && <p className="sec-loading">Собираем меню каждой должности…</p>}

      {data && mode === 'role' && (
        <ul className="preview-list">
          {roles.map(({ id, preview, nav }) => (
            <li key={id} className="preview-card">
              <div className="preview-card-head">
                <strong>{preview.roleLabel}</strong>
                <span>{ruCount(nav.length, 'раздел', 'раздела', 'разделов')}</span>
              </div>
              <SectionChips nav={nav} />
              <p className="preview-card-line">{punishLine(preview.staffPerms)}</p>
              <button type="button" className="preview-go" onClick={() => onOpen?.(preview)}>
                Войти в копию
              </button>
            </li>
          ))}
        </ul>
      )}

      {data && mode === 'person' && (
        <>
          <input
            className="sec-input preview-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Имя, @username или ID"
            aria-label="Найти сотрудника"
          />
          {people.length === 0 && (
            <p className="sec-empty">{total ? 'Никто не подошёл под поиск' : 'Сотрудников с настраиваемой должностью пока нет'}</p>
          )}
          <ul className="preview-list">
            {people.map(({ member, preview, nav }) => {
              const own = Object.keys(member.overrides || {}).length
              return (
                <li key={member.userId} className="preview-card">
                  <div className="preview-card-head">
                    <strong>{preview.name}</strong>
                    <span>{preview.roleLabel}</span>
                  </div>
                  <p className="preview-card-line">
                    {member.username ? `@${member.username} · ` : ''}ID {member.userId}
                  </p>
                  <p className="preview-card-line">
                    {ruCount(nav.length, 'раздел', 'раздела', 'разделов')}
                    {own ? ` · ${ruCount(own, 'личное исключение', 'личных исключения', 'личных исключений')}` : ' · как у должности'}
                  </p>
                  <p className="preview-card-line">{punishLine(preview.staffPerms)}</p>
                  <button type="button" className="preview-go" onClick={() => onOpen?.(preview)}>
                    Войти как {preview.name}
                  </button>
                </li>
              )
            })}
          </ul>
        </>
      )}
    </div>
  )
}
