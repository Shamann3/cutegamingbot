import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { fetchGroupOpen, submitGroupApplication } from '../lib/adminClient'
import { accentIsPersonal, loadStoredAccent } from '../lib/accentTheme'
import ChoiceSheet from '../components/ChoiceSheet'
import EntryFrame from '../components/EntryFrame'
import EntryGuide from '../components/EntryGuide'
import { SCREENS } from '../entry_design'
import { playMeme } from '../lib/memeSounds'

const RULES_CHANNEL = 'https://t.me/CuteRules'

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
const MAX_WORDS = 70

function countWords(value) {
  const clean = String(value || '').trim()
  if (!clean) return 0
  return clean.split(/\s+/).length
}

function wordsLabel(count) {
  const mod10 = count % 10
  const mod100 = count % 100
  if (mod10 === 1 && mod100 !== 11) return 'слово'
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'слова'
  return 'слов'
}

function groupHandle(username) {
  const clean = String(username || '').trim().replace(/^@/, '')
  return clean ? `@${clean}` : ''
}

function HiddenKey({ value }) {
  const [shown, setShown] = useState(false)
  if (!value) return null
  return (
    <button
      type="button"
      className="apply-key"
      aria-pressed={shown}
      onClick={() => setShown((open) => !open)}
    >
      <span className="apply-key-name">Ключ входа</span>
      <code className={shown ? 'apply-key-value is-open' : 'apply-key-value'}>
        {shown ? value : '• • • •   • • • •   • • • •'}
      </code>
      <span className="apply-key-hint">{shown ? 'Нажмите ещё раз, чтобы скрыть' : 'Нажмите, чтобы открыть'}</span>
    </button>
  )
}

function symbolsLeft(count) {
  const mod10 = count % 10
  const mod100 = count % 100
  const word = mod10 === 1 && mod100 !== 11
    ? 'символ'
    : mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)
      ? 'символа'
      : 'символов'
  return `Ещё ${count} ${word}`
}

function sendFailure(err) {
  const message = String(err?.message || '').trim()
  if (!message || message === 'API не отвечает' || /^Ошибка \d+$/.test(message)) {
    return 'Заявка не ушла. Нажмите ещё раз.'
  }
  if (/admin-бота|Сессия Telegram|Откройте панель/.test(message)) {
    return 'Заявка записывается на вас из Telegram. Откройте панель через CuteGamingBot и отправьте её ещё раз.'
  }
  return message
}

function showInCard(node) {
  const card = node?.closest?.('.entry-stable')
  if (!node || !card || typeof card.scrollTo !== 'function') return
  const delta = node.getBoundingClientRect().top - card.getBoundingClientRect().top - 12
  if (Math.abs(delta) > 2) card.scrollTo({ top: Math.max(0, card.scrollTop + delta), behavior: 'auto' })
}

const STATUS_LABEL = {
  pending: 'На рассмотрении',
  rejected: 'Отклонена',
  approved: 'Принята',
}

export default function GroupApplyPage({ onBack, preview = false }) {
  const personal = accentIsPersonal(loadStoredAccent())
  const [error, setError] = useState('')
  const [listState, setListState] = useState(preview ? 'ready' : 'loading')
  const [positions, setPositions] = useState([])
  const [mine, setMine] = useState([])
  const [chatId, setChatId] = useState(null)
  const [positionId, setPositionId] = useState(null)
  const usefulHeard = useRef(false)
  useEffect(() => {
    if (!positionId || usefulHeard.current) return
    usefulHeard.current = true
    playMeme('useful')
  }, [positionId])
  const [body, setBody] = useState('')
  const nextRef = useRef(null)
  const resultRef = useRef(null)
  const sendingRef = useRef(false)
  const aliveRef = useRef(true)
  const [sheet, setSheet] = useState(null)
  const [rulesKnown, setRulesKnown] = useState(false)
  const [sending, setSending] = useState(false)
  const [done, setDone] = useState(false)
  const [sent, setSent] = useState(null)

  const loadOpen = useCallback((quiet = true) => {
    if (preview) return
    if (!quiet) setListState('loading')
    fetchGroupOpen()
      .then((data) => {
        if (!aliveRef.current) return
        setPositions(Array.isArray(data?.positions) ? data.positions : [])
        setMine(Array.isArray(data?.mine) ? data.mine : [])
        setListState('ready')
      })
      .catch(() => {
        if (!aliveRef.current) return
        setListState((state) => (state === 'ready' ? 'ready' : 'down'))
      })
  }, [preview])

  useEffect(() => {
    aliveRef.current = true
    if (preview) {
      setPositions(PREVIEW_POSITIONS)
      setListState('ready')
      setError('')
      return () => { aliveRef.current = false }
    }
    loadOpen()
    const timer = window.setInterval(() => loadOpen(), 8000)
    return () => {
      aliveRef.current = false
      window.clearInterval(timer)
    }
  }, [preview, loadOpen])

  const text = body.trim()
  const words = countWords(text)
  const tooMany = words > MAX_WORDS
  const enough = text.length >= MIN_BODY && !tooMany
  const canSend = rulesKnown && Boolean(chatId) && Boolean(positionId) && enough

  useLayoutEffect(() => {
    if (!done && !error && !sending) return
    showInCard(resultRef.current)
  }, [done, error, sending])

  useEffect(() => {
    if (!canSend) return undefined
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
  }, [canSend])

  const chats = useMemo(() => {
    const map = new Map()
    positions.forEach((item) => {
      if (!map.has(item.chatId)) {
        map.set(item.chatId, {
          chatId: item.chatId,
          title: item.title,
          username: item.username || '',
          roles: [],
        })
      }
      map.get(item.chatId).roles.push(item)
    })
    return [...map.values()]
  }, [positions])

  const roles = chats.find((chat) => chat.chatId === chatId)?.roles || []
  const chosen = roles.find((role) => role.positionId === positionId) || null
  const keyed = mine.some((item) => item.status === 'approved' && item.entryKey)
  const guideAt = keyed ? 'enter' : done ? 'key' : !rulesKnown ? 'rules' : !positionId ? 'pick' : 'about'

  const submit = async (event) => {
    event?.preventDefault?.()
    if (sendingRef.current) return
    if (!chosen) {
      setError('Выберите группу и должность')
      return
    }
    if (tooMany) {
      const over = words - MAX_WORDS
      setError(`Слишком длинно: уберите ${over} ${wordsLabel(over)}. Можно не больше ${MAX_WORDS} слов.`)
      return
    }
    if (!enough) {
      setError(symbolsLeft(MIN_BODY - text.length))
      return
    }
    if (!rulesKnown) {
      setError('Сначала отметьте «Я знаю правила»')
      return
    }
    const receipt = {
      group: chats.find((chat) => chat.chatId === chosen.chatId)?.title || 'Группа',
      position: chosen.position,
    }
    sendingRef.current = true
    setSending(true)
    setError('')
    if (preview) {
      setSent(receipt)
      setDone(true)
      sendingRef.current = false
      setSending(false)
      return
    }
    try {
      const data = await submitGroupApplication({
        chat_id: chosen.chatId,
        position_id: chosen.positionId,
        body: text,
        rules_read: true,
      })
      if (!data?.ok || !data?.id) throw new Error('Заявка не ушла. Нажмите ещё раз.')
      setSent(receipt)
      setMine((list) => [
        {
          id: data.id,
          status: 'pending',
          group: receipt.group,
          position: receipt.position,
          note: '',
          entryKey: '',
        },
        ...list.filter((item) => item.id !== data.id),
      ])
      setDone(true)
    } catch (err) {
      setError(sendFailure(err))
    } finally {
      sendingRef.current = false
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

        <EntryGuide screen={SCREENS.groupApply} at={guideAt} />

        {done && sent && (
          <div className="apply-receipt" ref={resultRef} role="status">
            <strong>{preview ? 'Это показ' : 'Заявка отправлена'}</strong>
            <p>
              {preview
                ? `«${sent.group}», должность «${sent.position}». Это только показ: заявка никуда не ушла.`
                : `«${sent.group}», должность «${sent.position}». Она у создателя в разделе «Заявки». Когда он её примет, ключ придёт вам в бота. С этим ключом вы сами входите в панель администратора. Если заявку отклонят, в эту группу можно снова через 7 дней.`}
            </p>
          </div>
        )}

        {!done && (
          <form className="auth-form auth-step" onSubmit={submit}>
            <div className="apply-rules">
              <p className="apply-rules-title">Прочтите правила</p>
              <a className="auth-btn auth-btn-primary" href={RULES_CHANNEL} target="_blank" rel="noreferrer">
                Канал с правилами
              </a>
              <p className="apply-rules-note">
                При открытии правил нужно будет перезайти в панель и написать заявку заново.
              </p>
              <p className="apply-rules-ask">Вы ознакомлены с правилами проекта?</p>
              <label className="apply-rules-check">
                <input
                  type="checkbox"
                  checked={rulesKnown}
                  onChange={(event) => {
                    const on = event.target.checked
                    setRulesKnown(on)
                    if (!on) {
                      setChatId(null)
                      setPositionId(null)
                      setBody('')
                      setSheet(null)
                    }
                    setError('')
                  }}
                />
                <span>Я знаю правила</span>
              </label>
            </div>
            <div className={`auth-reveal-slot${rulesKnown ? ' is-open' : ''}`} aria-hidden={rulesKnown ? undefined : true}>
              <div className="auth-reveal-inner">
                {chats.length > 0 ? (
                  <ChoiceSheet
                    prompt="Выберите группу, в которой вы хотите работать"
                    value={chatId}
                    options={chats.map((chat) => ({
                      id: chat.chatId,
                      label: chat.title,
                      detail: groupHandle(chat.username),
                    }))}
                    open={sheet === 'group'}
                    onOpen={() => setSheet('group')}
                    onClose={() => setSheet(null)}
                    onChange={(id) => {
                      setChatId(id)
                      setPositionId(null)
                      setBody('')
                      setSheet(null)
                      setError('')
                    }}
                  />
                ) : (
                  <div className="apply-step">
                    <p className="apply-hint">
                      {listState === 'loading'
                        ? 'Группы ещё открываются.'
                        : listState === 'down'
                          ? 'Группы не открылись.'
                          : 'Набор закрыт. Создатель ещё не открыл группу.'}
                    </p>
                    {listState === 'down' && (
                      <button type="button" className="auth-btn auth-btn-primary" onClick={() => loadOpen(false)}>
                        Открыть ещё раз
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>

            <div className={`auth-reveal-slot${chatId ? ' is-open' : ''}`} aria-hidden={chatId ? undefined : true}>
              <div className="auth-reveal-inner">
                <ChoiceSheet
                  prompt="Выберите, на какую именно должность вы рассчитываете"
                  value={positionId}
                  options={roles.map((role) => ({
                    id: role.positionId,
                    label: role.held ? `${role.position} · ваша должность` : role.position,
                  }))}
                  open={sheet === 'position'}
                  onOpen={() => setSheet('position')}
                  onClose={() => setSheet(null)}
                  onChange={(id) => {
                    setPositionId(id)
                    setBody('')
                    setSheet(null)
                    setError('')
                  }}
                />
              </div>
            </div>

            <div className={`auth-reveal-slot${positionId ? ' is-open' : ''}`} aria-hidden={positionId ? undefined : true}>
              <div className="auth-reveal-inner">
                {chosen?.held && (
                  <p className="realm-copy">Эта должность уже ваша. Заявка нужна, чтобы создатель выдал ключ.</p>
                )}
                {chosen && (
                  <p className="realm-copy">
                    Права: {(chosen.rights || []).map((right) => RIGHT_LABEL[right] || right).join(', ')}
                  </p>
                )}
                <label className="auth-field">
                  <span className="auth-form-lead">Напишите, чем вы полезны для группы, которую вы выбрали</span>
                  <textarea
                    className="auth-input"
                    value={body}
                    onChange={(e) => setBody(e.target.value)}
                    rows={4}
                    placeholder="До 70 слов о себе"
                  />
                </label>
                <p className={`apply-hint${tooMany ? ' is-over' : ''}`}>
                  {tooMany
                    ? `Слишком длинно: ${words} из ${MAX_WORDS} слов. Уберите ${words - MAX_WORDS} ${wordsLabel(words - MAX_WORDS)}.`
                    : words === 0
                      ? `До ${MAX_WORDS} слов о себе`
                      : text.length < MIN_BODY
                        ? `${symbolsLeft(MIN_BODY - text.length)}. Не больше ${MAX_WORDS} слов.`
                        : `${words} из ${MAX_WORDS} слов`}
                </p>
              </div>
            </div>

            <div className={`auth-reveal-slot${canSend ? ' is-open' : ''}`} aria-hidden={canSend ? undefined : true} ref={nextRef}>
              <div className="auth-reveal-inner">
                <div className="apply-step">
                  <button type="submit" className="auth-btn auth-btn-primary" disabled={sending} onClick={submit}>
                    {sending ? 'Отправка…' : 'Отправить заявку'}
                  </button>
                </div>
              </div>
            </div>
            {(sending || error) && (
              <p className="apply-sent-error" role={error ? 'alert' : 'status'} ref={resultRef}>
                {error || 'Заявка уходит создателю.'}
              </p>
            )}
          </form>
        )}

        {mine.length > 0 && (
          <ul className="realm-list">
            {mine.map((item) => (
              <li key={item.id}>
                <div className="realm-row">
                  <strong>{item.group ? `${item.group}${item.position ? ` · ${item.position}` : ''}` : `Заявка ${item.id}`}</strong>
                  <span>{STATUS_LABEL[item.status] || item.status}{item.note ? ` · ${item.note}` : ''}</span>
                  {item.entryKey ? <HiddenKey value={item.entryKey} /> : null}
                </div>
              </li>
            ))}
          </ul>
        )}

    </EntryFrame>
  )
}
