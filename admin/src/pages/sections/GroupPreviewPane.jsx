import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchRightsBoard } from '../../lib/adminClient'
import {
  GROUP_PUNISH_LABELS,
  groupCabinetTabs,
  groupPeople,
  groupPersonPreview,
  groupPositionPreview,
  ruCount,
} from '../../lib/panelPreview'

const MODES = [
  { id: 'role', label: 'Должность' },
  { id: 'person', label: 'Администратор' },
]

function punishLine(rights) {
  const names = (rights || []).filter((key) => GROUP_PUNISH_LABELS[key]).map((key) => GROUP_PUNISH_LABELS[key])
  return names.length ? `Наказания: ${names.join(', ')}` : 'Наказаний нет'
}

function PageChips({ rights }) {
  return (
    <ul className="preview-chips" aria-label="Страницы кабинета">
      {groupCabinetTabs(rights, false).map((item) => <li key={item.id}>{item.label}</li>)}
    </ul>
  )
}

export default function GroupPreviewPane({ onOpen }) {
  const [mode, setMode] = useState('role')
  const [groups, setGroups] = useState([])
  const [chatId, setChatId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchRightsBoard()
      const list = Array.isArray(data?.groups) ? data.groups : []
      setGroups(list)
      setChatId((prev) => (list.some((group) => group.chatId === prev) ? prev : list[0]?.chatId ?? null))
      setLoaded(true)
    } catch (err) {
      setError(err?.message || 'Группы и должности не открылись')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const current = groups.find((group) => group.chatId === chatId) || null
  const people = useMemo(() => groupPeople(groups), [groups])
  const seatsKnown = groups.some((group) => Array.isArray(group.seats))
  const found = useMemo(() => {
    const needle = query.trim().toLowerCase().replace(/^@/, '')
    if (!needle) return people
    return people.filter((person) => String(person.userId).includes(needle)
      || person.name.toLowerCase().includes(needle)
      || String(person.username || '').toLowerCase().includes(needle)
      || person.groups.some((group) => String(group.title).toLowerCase().includes(needle)))
  }, [people, query])

  const seated = (positionId) => (current?.seats || []).filter((seat) => seat.positionId === positionId).length

  return (
    <div className="preview-desk">
      <p className="staff-hint">
        Копия открывает кабинет группы так, как его видит должность или конкретный администратор:
        те же группы, страницы и наказания. Это тестовый режим — смотреть можно всё, а наказания и правки не отправляются.
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
              {item.id === 'person' && people.length ? `${item.label} · ${people.length}` : item.label}
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
      {loading && !loaded && <p className="sec-loading">Собираем группы и должности…</p>}
      {loaded && groups.length === 0 && (
        <p className="sec-empty">Официальных групп пока нет. Когда группа станет официальной, её должности появятся здесь.</p>
      )}

      {loaded && groups.length > 0 && mode === 'role' && (
        <>
          {groups.length > 1 && (
            <nav className="sec-tabs preview-groups" aria-label="Группа">
              {groups.map((group) => (
                <button
                  key={group.chatId}
                  type="button"
                  className={`sec-tab${group.chatId === chatId ? ' sec-tab-active' : ''}`}
                  aria-current={group.chatId === chatId ? 'page' : undefined}
                  onClick={() => setChatId(group.chatId)}
                >
                  {group.title}
                </button>
              ))}
            </nav>
          )}
          {current && (current.positions || []).length === 0 && (
            <p className="sec-empty">В этой группе нет должностей. Создайте их во вкладке «Должности».</p>
          )}
          <ul className="preview-list">
            {(current?.positions || []).map((position) => {
              const count = seated(position.id)
              return (
                <li key={position.id} className="preview-card">
                  <div className="preview-card-head">
                    <strong>{position.title}</strong>
                    <span>ранг {position.rank}</span>
                  </div>
                  <PageChips rights={position.rights} />
                  <p className="preview-card-line">{punishLine(position.rights)}</p>
                  {seatsKnown && (
                    <p className="preview-card-line">
                      {count ? `На должности ${ruCount(count, 'человек', 'человека', 'человек')}` : 'На должности пока никого'}
                    </p>
                  )}
                  <button type="button" className="preview-go" onClick={() => onOpen?.(groupPositionPreview(current, position))}>
                    Войти в копию
                  </button>
                </li>
              )
            })}
          </ul>
        </>
      )}

      {loaded && groups.length > 0 && mode === 'person' && (
        <>
          {!seatsKnown && (
            <p className="sec-empty">Сервер панели ещё не отдаёт список администраторов. После его обновления люди появятся здесь.</p>
          )}
          {seatsKnown && (
            <input
              className="sec-input preview-search"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Имя, @username, ID или группа"
              aria-label="Найти администратора"
            />
          )}
          {seatsKnown && found.length === 0 && (
            <p className="sec-empty">{people.length ? 'Никто не подошёл под поиск' : 'Администраторов групп пока нет'}</p>
          )}
          <ul className="preview-list">
            {found.map((person) => (
              <li key={person.userId} className="preview-card">
                <div className="preview-card-head">
                  <strong>{person.name}</strong>
                  <span>{ruCount(person.groups.length, 'группа', 'группы', 'групп')}</span>
                </div>
                <p className="preview-card-line">
                  {person.username ? `@${person.username} · ` : ''}ID {person.userId}
                  {person.staff ? ' · ещё и сотрудник проекта' : ''}
                </p>
                <ul className="preview-chips" aria-label="Группы и должности">
                  {person.groups.map((group) => (
                    <li key={group.chatId}>{group.title} — {group.position}</li>
                  ))}
                </ul>
                <button type="button" className="preview-go" onClick={() => onOpen?.(groupPersonPreview(person))}>
                  Войти как {person.name}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
