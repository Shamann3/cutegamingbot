import { useEffect, useMemo, useState } from 'react'
import { fetchGroupOpen, submitGroupApplication } from '../lib/adminClient'
import { accentIsPersonal, loadStoredAccent } from '../lib/accentTheme'

const RIGHT_LABEL = {
  view_members: 'участники',
  view_archive: 'архив',
  view_analytics: 'аналитика',
  punish_mute: 'мут',
  punish_ban: 'бан',
  punish_kick: 'кик',
  punish_warn: 'варн',
  punish_voice: 'голос',
  manage_positions: 'должности',
}

export default function GroupApplyPage({ onBack }) {
  const personal = accentIsPersonal(loadStoredAccent())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [positions, setPositions] = useState([])
  const [mine, setMine] = useState([])
  const [chatId, setChatId] = useState(null)
  const [positionId, setPositionId] = useState(null)
  const [body, setBody] = useState('')
  const [rules, setRules] = useState(false)
  const [sending, setSending] = useState(false)
  const [done, setDone] = useState(false)

  const load = () => {
    setLoading(true)
    setError('')
    fetchGroupOpen()
      .then((data) => {
        setPositions(Array.isArray(data?.positions) ? data.positions : [])
        setMine(Array.isArray(data?.mine) ? data.mine : [])
      })
      .catch((err) => setError(err.message || 'Список групп не открылся'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const chats = useMemo(() => {
    const map = new Map()
    positions.forEach((item) => {
      if (!map.has(item.chatId)) map.set(item.chatId, { chatId: item.chatId, title: item.title, roles: [] })
      map.get(item.chatId).roles.push(item)
    })
    return [...map.values()]
  }, [positions])

  const roles = chats.find((chat) => chat.chatId === chatId)?.roles || []
  const chosen = roles.find((role) => role.positionId === positionId) || null

  const submit = async (event) => {
    event.preventDefault()
    if (!chosen) {
      setError('Выберите группу и должность')
      return
    }
    if (!rules) {
      setError('Откройте правила и отметьте, что прочитали их')
      return
    }
    if (body.trim().length < 20) {
      setError('Напишите, чем будете полезны этому чату. Минимум 20 символов')
      return
    }
    setSending(true)
    setError('')
    try {
      await submitGroupApplication({
        chat_id: chosen.chatId,
        position_id: chosen.positionId,
        body: body.trim(),
        rules_read: true,
      })
      setDone(true)
    } catch (err) {
      setError(err.message || 'Заявка не отправилась')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className={`gate-root${personal ? ' is-personal' : ''}`}>
      <div className="gate-frame" aria-hidden="true" />
      <div className="gate-sheet">
        <header className="gate-head">
          <h1 className="gate-title">Заявка в группу</h1>
          <p className="gate-lead">Только официальная группа и должность, на которую открыт набор. Это не делает вас сотрудником проекта.</p>
        </header>

        {loading && <p className="gate-status">Сверяем набор…</p>}
        {error && (
          <div className="gate-recover" role="alert">
            <p className="gate-status gate-status-error">{error}</p>
            <button type="button" className="gate-text" onClick={load}>Повторить</button>
          </div>
        )}

        {!loading && done && (
          <p className="gate-lead">Заявка отправлена. Вход в кабинет откроется после решения создателя. Повторно в ту же группу её не отправляют.</p>
        )}

        {!loading && !done && chats.length === 0 && !error && (
          <p className="gate-status">Набор закрыт: создатель ещё не открыл официальную группу.</p>
        )}

        {!loading && !done && chats.length > 0 && (
          <form className="realm-form" onSubmit={submit}>
            <label>
              Группа
              <select value={chatId ?? ''} onChange={(e) => { setChatId(Number(e.target.value)); setPositionId(null) }}>
                <option value="">Выберите</option>
                {chats.map((chat) => (
                  <option key={chat.chatId} value={chat.chatId}>{chat.title}</option>
                ))}
              </select>
            </label>
            <label>
              Должность
              <select value={positionId ?? ''} onChange={(e) => setPositionId(Number(e.target.value))} disabled={!chatId}>
                <option value="">Выберите</option>
                {roles.map((role) => (
                  <option key={role.positionId} value={role.positionId}>{role.position}</option>
                ))}
              </select>
            </label>
            {chosen && (
              <p className="realm-copy">
                Права: {chosen.rights.map((right) => RIGHT_LABEL[right] || right).join(', ')}
              </p>
            )}
            <label>
              Чем полезны этому чату
              <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={4} />
            </label>
            <a href="https://t.me/CuteRules" target="_blank" rel="noreferrer">Открыть правила CuteRules</a>
            <label className="realm-check">
              <input type="checkbox" checked={rules} onChange={(e) => setRules(e.target.checked)} />
              Правила прочитаны
            </label>
            <button type="submit" className="realm-back" disabled={sending}>
              {sending ? 'Отправка…' : 'Отправить заявку'}
            </button>
          </form>
        )}

        {mine.length > 0 && (
          <ul className="realm-list">
            {mine.map((item) => (
              <li key={item.id}>
                <div className="realm-row">
                  <strong>Заявка {item.id}</strong>
                  <span>{item.status}{item.note ? ` · ${item.note}` : ''}</span>
                </div>
              </li>
            ))}
          </ul>
        )}

        <button type="button" className="gate-text" onClick={onBack}>К выбору панели</button>
      </div>
    </div>
  )
}
