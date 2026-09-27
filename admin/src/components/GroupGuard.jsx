import { useEffect, useState } from 'react'
import { fetchGroupGuard, saveGroupGuard } from '../lib/adminClient'
import RightSwitch from './RightSwitch'

const KINDS = { link: 'Ссылка', flood: 'Флуд', captcha: 'Капча' }

export default function GroupGuard({ chatId, creator }) {
  const [pack, setPack] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')

  const load = () => {
    if (!chatId) return
    setError('')
    fetchGroupGuard(chatId)
      .then((data) => setPack(data))
      .catch((err) => setError(err.message || 'Защита не открылась'))
  }

  useEffect(() => { load() }, [chatId])

  if (!chatId) return null

  const save = async (next) => {
    setBusy('save')
    setError('')
    try {
      setPack(await saveGroupGuard(chatId, next))
    } catch (err) {
      setError(err.message || 'Правило не сохранилось')
    } finally {
      setBusy('')
    }
  }

  const on = {
    captcha: Boolean(pack?.captcha),
    links: Boolean(pack?.links),
    flood: Boolean(pack?.flood),
  }

  return (
    <section className="shift-desk">
      <header className="guard-head">
        <h2 className="realm-h">Защита этой группы</h2>
        <p className="realm-copy">
          {creator
            ? (pack?.custom
              ? 'Здесь своё правило, только для этой группы. Общие правила живут в панели сотрудников, раздел «Защита».'
              : 'Сейчас группа повторяет общие правила. Они в панели сотрудников, раздел «Защита». Если сдвинете переключатель, правило станет своим.')
            : 'Правила включает создатель проекта. В своей группе должность и так может писать ссылки.'}
        </p>
      </header>
      {error && <p className="realm-alert" role="alert">{error}</p>}
      <RightSwitch
        on={on.captcha}
        disabled={!creator || busy === 'save'}
        title="Капча"
        hint="Новый человек проходит проверку, прежде чем писать"
        onChange={(value) => save({ ...on, captcha: value })}
      />
      <RightSwitch
        on={on.links}
        disabled={!creator || busy === 'save'}
        title="Ссылки и пересылки"
        hint="Чужие ссылки и пересланные сообщения бот убирает"
        onChange={(value) => save({ ...on, links: value })}
      />
      <RightSwitch
        on={on.flood}
        disabled={!creator || busy === 'save'}
        title="Антифлуд"
        hint="Шесть сообщений за восемь секунд бот убирает"
        onChange={(value) => save({ ...on, flood: value })}
      />
      {creator && pack?.custom && (
        <button type="button" className="realm-back" disabled={busy === 'save'} onClick={() => save({ follow: true })}>
          Снова как у всех
        </button>
      )}
      <h3 className="realm-h">Кого поймали</h3>
      {(pack?.hits || []).length === 0 && <p className="realm-copy">Пока пусто.</p>}
      <ul className="realm-list">
        {(pack?.hits || []).map((hit, index) => (
          <li key={`${hit.at || index}-${hit.userId || index}`} className="realm-row">
            <strong>{KINDS[hit.kind] || hit.kind} · {hit.userId ? `#${hit.userId}` : '—'}</strong>
            <span>{hit.detail || ''}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
