import { useCallback, useEffect, useState } from 'react'
import CountUp from '../../../components/CountUp'
import { fetchDeedWork, isPanelPreviewMode, sortDeed, unsortDeed } from '../../../lib/adminClient'
import { BAND_LABEL, SORT_LABEL, admins, waitCaption } from '../../../lib/deedSort'
import useSwipeDeck, { deckKey } from '../../../lib/useSwipeDeck'
import DeckCard, { FLY_MS, motionQuiet, useToastInView, wait } from './DeckCard'

const CHOICES = [
  { id: 'wrong', label: SORT_LABEL.wrong, hint: 'не то фото или не тот человек', side: 'left' },
  { id: 'weak', label: SORT_LABEL.weak, hint: 'передать другим и создателю', side: 'down' },
  { id: 'clear', label: SORT_LABEL.clear, hint: 'доказательство на месте', side: 'right' },
]

const BY_SIDE = { left: CHOICES[0], down: CHOICES[1], right: CHOICES[2] }

const STAMPS = CHOICES.map((choice) => ({ side: choice.side, label: choice.label }))

const DONE_TEXT = {
  clear: 'Подходит. Отправлено создателю: такие наказания он смотрит первыми.',
  wrong: 'Не подходит. Создатель увидит ваш ответ и решит сам.',
  weak: 'Непонятно. Наказание ушло дальше: его посмотрят другие администраторы и создатель.',
}

function messageOf(error) {
  return error?.message || 'Не удалось открыть проверку'
}

function unclearNote(card) {
  const n = Number(card?.unclearCount) || 0
  if (!n) return ''
  return n === 1
    ? 'Другой администратор не смог решить. Нужен ваш взгляд.'
    : `${admins(n)} не смогли решить. Нужен ваш взгляд.`
}

export default function WorkDesk({ onCount }) {
  const [queue, setQueue] = useState(null)
  const [error, setError] = useState('')
  const [flash, setFlash] = useState(null)
  const [busy, setBusy] = useState(false)
  const [fly, setFly] = useState(null)
  const [back, setBack] = useState(null)

  const load = useCallback(async () => {
    if (isPanelPreviewMode()) return
    try {
      const data = await fetchDeedWork()
      setQueue(data)
      setError('')
      onCount?.(Number(data?.waiting) || 0)
    } catch (err) {
      setError(messageOf(err))
      onCount?.(0)
    }
  }, [onCount])

  useEffect(() => { load() }, [load])

  const card = queue?.card
  const toastRef = useToastInView(flash?.key)
  const swipe = useSwipeDeck({
    onSwipe: (side) => choose(BY_SIDE[side]),
    disabled: busy || Boolean(fly) || !card,
    cardKey: card?.id ?? null,
  })
  const { reset } = swipe

  const run = useCallback(async (id, choice) => {
    setBusy(true)
    setError('')
    setBack(null)
    if (!motionQuiet()) {
      setFly({ id, side: choice.side })
      await wait(FLY_MS)
    }
    let failure = ''
    try {
      await sortDeed(id, choice.id)
    } catch (err) {
      failure = messageOf(err)
      reset()
    }
    await load()
    if (failure) setError(failure)
    else setFlash({ key: Date.now(), text: DONE_TEXT[choice.id], undoId: id, side: choice.side })
    setFly(null)
    setBusy(false)
  }, [load, reset])

  const choose = useCallback((choice) => {
    const id = card?.id
    if (!id || !choice || busy || fly) return false
    run(id, choice)
    return true
  }, [card, busy, fly, run])

  const undo = useCallback(async () => {
    const last = flash
    if (!last?.undoId || busy || fly) return
    setBusy(true)
    setError('')
    let failure = ''
    try {
      await unsortDeed(last.undoId)
      setBack({ id: last.undoId, side: last.side })
    } catch (err) {
      failure = messageOf(err)
    }
    await load()
    if (failure) {
      setError(failure)
      setFlash({ ...last, undoId: 0 })
    } else {
      setFlash({ key: Date.now(), text: 'Ответ отменён. Карточка снова перед вами.', undoId: 0 })
    }
    setBusy(false)
  }, [flash, busy, fly, load])

  useEffect(() => {
    const onKey = (event) => {
      const key = deckKey(event)
      if (!key) return
      if (key === 'undo') {
        if (!flash?.undoId) return
        event.preventDefault()
        undo()
        return
      }
      if (choose(BY_SIDE[key])) event.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [choose, undo, flash])

  if (isPanelPreviewMode()) {
    return <p className="realm-copy">В копии панели наказания не проверяют. Это делается в настоящем кабинете.</p>
  }

  const locked = busy || Boolean(fly)
  const waiting = Number(queue?.waiting) || 0
  const flySide = fly && card && fly.id === card.id ? fly.side : ''
  const backSide = back && card && back.id === card.id ? back.side : ''

  const notes = (
    <>
      {flash && (
        <p ref={toastRef} key={flash.key} className="deed-flash deck-toast" role="status">
          <span>{flash.text}</span>
          {flash.undoId ? (
            <button type="button" className="sec-btn sec-btn-ghost deed-undo" disabled={locked} onClick={undo}>
              Вернуть
            </button>
          ) : null}
        </p>
      )}
      {error && <p className="staff-hint deck-error" role="alert">{error}</p>}
    </>
  )

  return (
    <div className="work-desk">
      <div className={`work-grid${card ? ' has-card' : ''}`}>
        <div className="work-head deck-copy">
          {waiting > 0 && (
            <div className="deck-count">
              <CountUp className="deed-sum" value={waiting} />
              <span className="deck-count-cap">{waitCaption(waiting, 'вашей проверки')}</span>
            </div>
          )}
          <p className="deed-lead">
            Здесь наказания, которые выдали другие администраторы. Посмотрите доказательство и ответьте, подходит ли наказание.
          </p>
          <p className="deck-why">
            Проверенные наказания быстрее доходят до создателя и до зарплаты. Ваши так же проверяют коллеги, поэтому своих вы здесь не увидите.
          </p>
          {!card && notes}
          {!queue && !error && <p className="staff-hint">Открываем наказания…</p>}
          {queue && !card && !error && (
            <p className="work-empty">Сейчас проверять нечего. Новые наказания коллег появятся здесь.</p>
          )}
          {card && (
            <p className="work-keys">
              Потяните карточку: вправо — подходит, влево — не подходит, вниз — непонятно.
              {card.hasProof && card.proofMediaId ? ' Нажмите на фото, чтобы открыть его целиком.' : ''}
              <span className="deck-keys-only"> На клавиатуре: → подходит, ← не подходит, ↓ непонятно, Ctrl+Z — вернуть ответ.</span>
            </p>
          )}
        </div>
        {card && (
          <div className="deck-col">
            <DeckCard
              card={card}
              band={BAND_LABEL[card.band] || 'Наказание'}
              note={unclearNote(card)}
              stamps={STAMPS}
              depth={Math.max(0, Math.min(2, waiting - 1))}
              fly={flySide}
              back={backSide}
              swipe={swipe}
            />
            <div className="work-choice">
              {CHOICES.map((choice) => (
                <button
                  key={choice.id}
                  type="button"
                  className={`sec-btn sec-btn-ghost deck-btn is-${choice.id} work-${choice.id}`}
                  disabled={locked}
                  onClick={() => choose(choice)}
                >
                  <span>
                    {choice.side === 'left' && <span className="deck-arrow" aria-hidden="true">←</span>}
                    {choice.label}
                    {choice.side === 'right' && <span className="deck-arrow" aria-hidden="true">→</span>}
                    {choice.side === 'down' && <span className="deck-arrow" aria-hidden="true">↓</span>}
                  </span>
                  <small>{choice.hint}</small>
                </button>
              ))}
            </div>
            {notes}
          </div>
        )}
      </div>
    </div>
  )
}
