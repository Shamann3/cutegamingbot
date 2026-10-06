import { useCallback, useEffect, useState } from 'react'
import { fetchRightsBoard, markGroupOfficial, searchGroupsStudio } from '../../lib/adminClient'
import { typedChatId } from '../../lib/seatChoice'

function stats(group) {
  const posts = (group.positions || []).filter((post) => (post.kind || 'post') === 'post' && Number(post.rank) < 5)
  const seated = (group.seats || []).filter((person) => (person.kind || 'post') === 'post' && Number(person.rank) < 5)
  return { posts: posts.length, seated: seated.length }
}

export default function OfficialGroupsPane() {
  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState('')
  const [dropId, setDropId] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchRightsBoard()
      setGroups(Array.isArray(data?.groups) ? data.groups : [])
    } catch (err) {
      setError(err.message || 'Официальные группы не открылись')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const known = new Set(groups.map((group) => String(group.chatId)))

  const search = async (event) => {
    event.preventDefault()
    const text = query.trim()
    if (text.length < 2) {
      setError('Введите название, @username или id чата')
      return
    }
    setBusy('search')
    setError('')
    setNotice('')
    try {
      const data = await searchGroupsStudio(text)
      setHits(Array.isArray(data?.items) ? data.items : [])
    } catch (err) {
      setHits([])
      setError(err.message || 'Поиск не выполнился')
    } finally {
      setBusy('')
    }
  }

  const add = async (row) => {
    const chatId = Number(row.chat_id)
    setBusy(`add-${chatId}`)
    setError('')
    setNotice('')
    try {
      await markGroupOfficial({
        chat_id: chatId,
        title: row.name || String(chatId),
        username: row.username || '',
        official: true,
      })
      setNotice(`«${row.name || chatId}» официальная. В этом чате «кто админ» показывает её администраторов.`)
      setHits(null)
      setQuery('')
      await load()
    } catch (err) {
      setError(err.message || 'Не удалось отметить группу')
    } finally {
      setBusy('')
    }
  }

  const remove = async (group) => {
    setBusy(`drop-${group.chatId}`)
    setError('')
    setNotice('')
    try {
      await markGroupOfficial({
        chat_id: group.chatId,
        title: group.title || String(group.chatId),
        username: group.username || '',
        official: false,
      })
      setDropId(null)
      setNotice(`«${group.title}» больше не официальная. Кабинет закрыт. Должности и люди сохранены: если вернуть группу, они появятся снова.`)
      await load()
    } catch (err) {
      setError(err.message || 'Не удалось убрать группу')
    } finally {
      setBusy('')
    }
  }

  const manualId = typedChatId(query)
  const manualMissing = manualId != null && hits && !hits.some((row) => Number(row.chat_id) === manualId)

  return (
    <div className="sec-tab-body staff-apps staff-groups">
      <p className="staff-hint">
        Официальная группа — чат проекта. Её можно добавить и убрать здесь.
        В таком чате «кто админ» показывает администраторов этой группы.
        Сотрудники проекта открываются отдельной кнопкой в том же сообщении.
      </p>
      {error && <p className="sec-error" role="alert">{error}</p>}
      {notice && <p className="realm-note" role="status">{notice}</p>}

      <form className="staff-group-search" onSubmit={search}>
        <label>
          Найти чат
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Название, @username или id"
          />
        </label>
        <button type="submit" className="sec-btn sec-btn-sm" disabled={busy === 'search' || query.trim().length < 2}>
          {busy === 'search' ? 'Ищем…' : 'Найти'}
        </button>
      </form>

      {hits && (
        <ul className="staff-app-list">
          {hits.map((row) => {
            const already = known.has(String(row.chat_id))
            return (
              <li key={row.chat_id} className="staff-app-card">
                <div className="staff-app-head">
                  <strong>{row.name || row.chat_id}</strong>
                  <span>{already ? 'Уже официальная' : 'Найдена'}</span>
                </div>
                <p className="staff-app-meta">
                  {row.username ? `@${String(row.username).replace(/^@/, '')} · ` : ''}id {row.chat_id}
                </p>
                <div className="staff-app-actions">
                  <button
                    type="button"
                    className="sec-btn sec-btn-sm"
                    disabled={already || busy === `add-${row.chat_id}`}
                    onClick={() => add(row)}
                  >
                    {already ? 'Уже в списке' : (busy === `add-${row.chat_id}` ? 'Запись…' : 'Сделать официальной')}
                  </button>
                </div>
              </li>
            )
          })}
          {manualMissing && (
            <li className="staff-app-card">
              <div className="staff-app-head">
                <strong>Чат {manualId}</strong>
                <span>В поиске его нет</span>
              </div>
              <p className="staff-app-meta">Можно отметить id официальным, даже если чата ещё нет в базе.</p>
              <div className="staff-app-actions">
                <button
                  type="button"
                  className="sec-btn sec-btn-sm"
                  disabled={known.has(String(manualId)) || busy === `add-${manualId}`}
                  onClick={() => add({ chat_id: manualId, name: `Чат ${manualId}`, username: '' })}
                >
                  {known.has(String(manualId)) ? 'Уже в списке' : 'Сделать официальной'}
                </button>
              </div>
            </li>
          )}
          {hits.length === 0 && !manualMissing && (
            <li className="staff-app-card"><p className="staff-app-meta">Такого чата в базе нет. Если знаете id, введите его целиком.</p></li>
          )}
        </ul>
      )}

      <h3 className="realm-h">Сейчас официальные</h3>
      {loading && groups.length === 0 && <p className="sec-loading">Загрузка групп…</p>}
      {!loading && groups.length === 0 && !error && (
        <p className="sec-empty">Официальных групп пока нет. Найдите чат выше и отметьте его.</p>
      )}
      <ul className="staff-app-list">
        {groups.map((group) => {
          const count = stats(group)
          const open = dropId === group.chatId
          return (
            <li key={group.chatId} className="staff-app-card">
              <div className="staff-app-head">
                <strong>{group.title || group.chatId}</strong>
                <span>{count.seated} на должностях</span>
              </div>
              <p className="staff-app-meta">
                {group.username ? `@${String(group.username).replace(/^@/, '')} · ` : ''}
                id {group.chatId} · должностей администраторов: {count.posts}
              </p>
              <p className="staff-app-meta">«Кто админ» в этом чате покажет этих администраторов, не сотрудников проекта.</p>
              <div className="staff-app-actions">
                <button
                  type="button"
                  className="sec-btn sec-btn-ghost sec-btn-sm"
                  disabled={Boolean(busy)}
                  onClick={() => { setDropId(open ? null : group.chatId); setError('') }}
                >
                  {open ? 'Оставить' : 'Убрать из официальных'}
                </button>
              </div>
              {open && (
                <form className="staff-app-reject" onSubmit={(event) => { event.preventDefault(); remove(group) }}>
                  <p className="staff-app-meta">
                    Кабинет закроется. Должности и люди на них сохранятся: если вернуть группу, они появятся снова.
                  </p>
                  <button type="submit" className="sec-btn sec-btn-danger sec-btn-sm" disabled={busy === `drop-${group.chatId}`}>
                    {busy === `drop-${group.chatId}` ? 'Убираем…' : 'Да, убрать'}
                  </button>
                </form>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
