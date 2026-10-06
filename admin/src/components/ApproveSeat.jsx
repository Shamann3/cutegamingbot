import { useEffect, useMemo, useState } from 'react'
import { fetchRightsBoard } from '../lib/adminClient'
import { applicationPerson } from '../lib/applicationPerson'
import { adminSeatChoices } from '../lib/seatChoice'
import FocusWindow from './FocusWindow'

export default function ApproveSeat({ item, busy = false, error = '', onClose, onApprove }) {
  const [groups, setGroups] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [picked, setPicked] = useState(item?.positionId ?? null)
  const person = applicationPerson(item || {})
  const choices = useMemo(() => adminSeatChoices(groups || []), [groups])
  const selected = choices.flatMap((group) => group.posts.map((post) => ({ ...post, group: group.title })))
    .find((post) => Number(post.id) === Number(picked)) || null

  useEffect(() => {
    let stop = false
    fetchRightsBoard()
      .then((data) => { if (!stop) setGroups(data?.groups || []) })
      .catch((err) => { if (!stop) setLoadError(err.message || 'Список групп не открылся') })
    return () => { stop = true }
  }, [])

  const submit = (event) => {
    event.preventDefault()
    if (!selected || busy) return
    onApprove(selected.id)
  }

  return (
    <FocusWindow
      title="Куда посадить"
      subtitle={person.username ? `${person.title} · @${person.username}` : person.title}
      onClose={busy ? undefined : onClose}
      footer={(
        <button type="submit" form="seat-approve" className="sec-btn" disabled={!selected || busy}>
          {busy ? 'Запись…' : selected ? `Одобрить · ${selected.title}` : 'Выберите должность'}
        </button>
      )}
    >
      <form id="seat-approve" className="seat-approve" onSubmit={submit}>
        <p className="realm-copy">
          В заявке: «{item?.position || 'должность'}» в «{item?.group || 'группе'}».
          Можно оставить её или выбрать другую должность администратора в любой официальной группе.
          Создатель группы через заявку не назначается. Другие группы, где человек уже сидит, не снимаются.
        </p>
        {loadError && <p className="realm-alert" role="alert">{loadError}</p>}
        {error && <p className="realm-alert" role="alert">{error}</p>}
        {groups === null && !loadError && <p className="realm-copy">Собираем должности…</p>}
        {choices.map((group) => (
          <fieldset key={group.chatId} className="realm-rights-block">
            <legend>{group.title}</legend>
            {group.posts.length === 0 ? (
              <p className="realm-copy">Должностей администратора нет. Их добавляют во вкладке «Должности».</p>
            ) : (
              group.posts.map((post) => {
                const on = Number(picked) === Number(post.id)
                return (
                  <button
                    key={post.id}
                    type="button"
                    className={on ? 'seat-pick is-on' : 'seat-pick'}
                    aria-pressed={on}
                    onClick={() => setPicked(post.id)}
                  >
                    <strong>{post.title}</strong>
                    <span>ранг {post.rank}</span>
                  </button>
                )
              })
            )}
          </fieldset>
        ))}
      </form>
    </FocusWindow>
  )
}
