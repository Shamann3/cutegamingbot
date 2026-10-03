import { useEffect, useMemo, useRef, useState } from 'react'
import { fetchGroupOpen, fetchGroupRules, submitGroupApplication } from '../lib/adminClient'
import { accentIsPersonal, loadStoredAccent } from '../lib/accentTheme'
import ChoiceSheet from '../components/ChoiceSheet'
import EntryFrame from '../components/EntryFrame'
import RulesReader from '../components/RulesReader'

const PREVIEW_POSITIONS = [
  {
    chatId: -1001,
    title: 'CuteGaming',
    positionId: 1,
    position: 'Модератор',
    rights: ['view_members', 'punish_mute', 'punish_warn'],
  },
  {
    chatId: -1001,
    title: 'CuteGaming',
    positionId: 2,
    position: 'Администратор',
    rights: ['view_archive', 'punish_ban', 'punish_kick'],
  },
]

const RIGHT_LABEL = {
  view_members: 'участники',
  view_archive: 'архив',
  view_analytics: 'цифры',
  punish_mute: 'мут',
  punish_ban: 'бан',
  punish_kick: 'кик',
  punish_warn: 'варн',
  punish_voice: 'голос',
  manage_positions: 'должности',
}

const MIN_BODY = 20

function symbolsLeft(count) {
  const mod10 = count % 10
  const mod100 = count % 100
  const word = mod10 === 1 && mod100 !== 11
    ? 'символ'
    : mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)
      ? 'символа'
      : 'символов'
  return `Ещё ${count} ${word} — и откроются правила.`
}

const STATUS_LABEL = {
  pending: 'На рассмотрении',
  rejected: 'Отклонена',
  approved: 'Принята',
}

export default function GroupApplyPage({ onBack, preview = false }) {
  const personal = accentIsPersonal(loadStoredAccent())
  const [loading, setLoading] = useState(!preview)
  const [error, setError] = useState('')
  const [positions, setPositions] = useState([])
  const [mine, setMine] = useState([])
  const [chatId, setChatId] = useState(null)
  const [positionId, setPositionId] = useState(null)
  const [body, setBody] = useState('')
  const [textSettled, setTextSettled] = useState(false)
  const nextRef = useRef(null)
  const [sheet, setSheet] = useState(null)
  const [rules, setRules] = useState([])
  const [rulesError, setRulesError] = useState('')
  const [rulesLoading, setRulesLoading] = useState(false)
  const [rulesKnown, setRulesKnown] = useState(false)
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

  const loadRules = () => {
    setRulesLoading(true)
    setRulesError('')
    fetchGroupRules()
      .then((data) => {
        const messages = Array.isArray(data?.messages) ? data.messages : []
        setRules(messages)
        if (!messages.length) setRulesError('Канал правил не отдал сообщения')
      })
      .catch((err) => setRulesError(err.message || 'Канал правил не открылся'))
      .finally(() => setRulesLoading(false))
  }

  useEffect(() => {
    if (preview) {
      setPositions(PREVIEW_POSITIONS)
      setLoading(false)
      setError('')
      return undefined
    }
    load()
    return undefined
  }, [preview])

  const text = body.trim()
  const enough = text.length >= MIN_BODY

  useEffect(() => {
    if (!text) {
      setTextSettled(false)
      setRulesKnown(false)
      return undefined
    }
    const timer = window.setTimeout(() => setTextSettled(true), 450)
    return () => window.clearTimeout(timer)
  }, [text])

  useEffect(() => {
    if (!textSettled || !enough || rules.length || rulesLoading || rulesError) return undefined
    loadRules()
    return undefined
  }, [textSettled, enough, rules.length, rulesLoading, rulesError])

  useEffect(() => {
    if (!textSettled) return undefined
    const node = nextRef.current
    if (!node) return undefined
    const timer = window.setTimeout(() => {
      const card = node.closest('.entry-stable')
      if (!card) return
      const pad = 28
      const delta = node.getBoundingClientRect().bottom - (card.getBoundingClientRect().bottom - pad)
      if (delta > 1) card.scrollTo({ top: card.scrollTop + delta, behavior: 'smooth' })
    }, 580)
    return () => window.clearTimeout(timer)
  }, [textSettled, enough, rulesLoading, rulesError, rules.length])

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
    if (!enough) {
      setError(symbolsLeft(MIN_BODY - text.length))
      return
    }
    if (!rulesKnown || !rules.length) {
      setError('Сначала прочитайте все сообщения с правилами')
      return
    }
    setSending(true)
    setError('')
    if (preview) {
      setDone(true)
      setSending(false)
      return
    }
    try {
      await submitGroupApplication({
        chat_id: chosen.chatId,
        position_id: chosen.positionId,
        body: body.trim(),
        rules_read: true,
        rules_ids: rules.map((item) => item.id),
      })
      setDone(true)
    } catch (err) {
      setError(err.message || 'Заявка не отправилась')
    } finally {
      setSending(false)
    }
  }

  return (
    <EntryFrame
      title="Панель администратора"
      lead="Заявка в группу. Это не панель сотрудника."
      personal={personal}
      onBack={onBack}
    >
        {preview && (
          <p className="auth-form-lead">Это показ. Заявка никуда не отправится.</p>
        )}

        {loading && <p className="auth-checking">Сверяем набор…</p>}
        {error && (
          <div className="gate-recover" role="alert">
            <p className="gate-status gate-status-error">{error}</p>
            {!done && chats.length === 0 && (
              <button type="button" className="gate-text" onClick={load}>Повторить</button>
            )}
          </div>
        )}

        {!loading && done && (
          <p className="auth-form-lead">
            {preview
              ? 'Форма заполнена. Если создатель примет заявку, в следующий раз вход будет как у сотрудника: сначала ключ, потом код из приложения. Если отклонит — в эту группу можно снова через 7 дней.'
              : 'Заявка ушла создателю. Если её примут, зайдите снова: сначала ключ, потом код из приложения. Если отклонят, в эту группу можно снова через 7 дней.'}
          </p>
        )}

        {!loading && !done && chats.length === 0 && !error && (
          <p className="gate-status">Набор закрыт. Создатель ещё не открыл группу.</p>
        )}

        {!loading && !done && chats.length > 0 && (
          <form className="auth-form auth-step" onSubmit={submit}>
            <ChoiceSheet
              prompt="Выберите группу, в которой вы хотите работать"
              value={chatId}
              options={chats.map((chat) => ({ id: chat.chatId, label: chat.title }))}
              open={sheet === 'group'}
              onOpen={() => setSheet('group')}
              onClose={() => setSheet(null)}
              onChange={(id) => {
                setChatId(id)
                setPositionId(null)
                setSheet(null)
                setError('')
              }}
            />

            <div className={`auth-reveal-slot${chatId ? ' is-open' : ''}`} aria-hidden={chatId ? undefined : true}>
              <div className="auth-reveal-inner">
                <ChoiceSheet
                  prompt="Выберите, на какую именно должность вы рассчитываете"
                  value={positionId}
                  options={roles.map((role) => ({ id: role.positionId, label: role.position }))}
                  open={sheet === 'position'}
                  onOpen={() => setSheet('position')}
                  onClose={() => setSheet(null)}
                  onChange={(id) => {
                    setPositionId(id)
                    setSheet(null)
                    setError('')
                  }}
                />
              </div>
            </div>

            <div className={`auth-reveal-slot${positionId ? ' is-open' : ''}`} aria-hidden={positionId ? undefined : true}>
              <div className="auth-reveal-inner">
                {chosen && (
                  <p className="realm-copy">
                    Права: {chosen.rights.map((right) => RIGHT_LABEL[right] || right).join(', ')}
                  </p>
                )}
                <label className="auth-field">
                  <span className="auth-form-lead">Напишите, чем вы полезны для группы, которую вы выбрали</span>
                  <textarea className="auth-input" value={body} onChange={(e) => setBody(e.target.value)} rows={4} />
                </label>
              </div>
            </div>

            <div className={`auth-reveal-slot${textSettled ? ' is-open' : ''}`} aria-hidden={textSettled ? undefined : true}>
              <div className="auth-reveal-inner">
                <div className="apply-step" ref={nextRef}>
                  {!enough && <p className="apply-hint">{symbolsLeft(MIN_BODY - text.length)}</p>}
                  {enough && rulesLoading && <p className="auth-checking">Читаем сообщения канала правил…</p>}
                  {enough && rulesError && (
                    <div className="apply-note" role="alert">
                      <p>{rulesError}</p>
                      <button type="button" className="auth-btn auth-btn-primary" onClick={loadRules}>Повторить</button>
                    </div>
                  )}
                  {enough && rules.length > 0 && (
                    <RulesReader messages={rules} known={rulesKnown} onKnown={() => setRulesKnown(true)} />
                  )}
                </div>
              </div>
            </div>

            <div className={`auth-reveal-slot${rulesKnown ? ' is-open' : ''}`} aria-hidden={rulesKnown ? undefined : true}>
              <div className="auth-reveal-inner">
                <button type="submit" className="auth-btn auth-btn-primary" disabled={sending}>
                  {sending ? 'Отправка…' : 'Отправить заявку'}
                </button>
              </div>
            </div>
          </form>
        )}

        {mine.length > 0 && (
          <ul className="realm-list">
            {mine.map((item) => (
              <li key={item.id}>
                <div className="realm-row">
                  <strong>Заявка {item.id}</strong>
                  <span>{STATUS_LABEL[item.status] || item.status}{item.note ? ` · ${item.note}` : ''}</span>
                </div>
              </li>
            ))}
          </ul>
        )}

    </EntryFrame>
  )
}
