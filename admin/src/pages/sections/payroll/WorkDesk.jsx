import { useCallback, useEffect, useState } from 'react'
import CountUp from '../../../components/CountUp'
import { fetchDeedWork, isPanelPreviewMode, sortDeed, unsortDeed } from '../../../lib/adminClient'
import { BAND_LABEL, VERDICT_BUTTON, waitCaption } from '../../../lib/deedSort'
import useSwipeDeck, { deckKey } from '../../../lib/useSwipeDeck'
import DeckCard, { FLY_MS, motionQuiet, pinShellScroll, useRefill, useToastInView, useWarmProof, wait } from './DeckCard'

const CHOICES = [
  { id: 'wrong', label: VERDICT_BUTTON.wrong, stamp: 'Неправильно', hint: 'можно просить снять', side: 'left' },
  { id: 'weak', label: VERDICT_BUTTON.weak, stamp: 'Непонятно', hint: 'передать дальше по цепочке', side: 'down' },
  { id: 'clear', label: VERDICT_BUTTON.clear, stamp: 'Подходит', hint: 'доказательство на месте', side: 'right' },
]

const BY_SIDE = { left: CHOICES[0], down: CHOICES[1], right: CHOICES[2] }

const STAMPS = CHOICES.map((choice) => ({ side: choice.side, label: choice.stamp }))

function doneText(choice, next) {
  const staff = next !== 'creator'
  if (choice === 'clear') {
    return staff
      ? 'Подходит. Сотрудник проекта увидит ваш ответ и проверит следом.'
      : 'Подходит. Сотрудников проекта сейчас нет, поэтому карточка сразу у создателя.'
  }
  if (choice === 'wrong') {
    return staff
      ? 'Наказание выдано неправильно. Сотрудник увидит это и сможет подать заявку на разблокировку.'
      : 'Наказание выдано неправильно. Сотрудников проекта нет, поэтому это сразу увидит создатель.'
  }
  return staff
    ? 'Непонятно. Карточка ушла сотруднику проекта, затем её увидит создатель. Другие администраторы её уже не увидят.'
    : 'Непонятно. Сотрудников проекта нет, поэтому карточку сразу увидит создатель.'
}

function messageOf(error) {
  return error?.message || 'Не удалось открыть проверку'
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
  useRefill(queue, load)
  useWarmProof(queue?.nextProofMediaId)

  const card = queue?.card
  const toastRef = useToastInView()
  const swipe = useSwipeDeck({
    onSwipe: (side) => choose(BY_SIDE[side]),
    disabled: busy || Boolean(fly) || !card,
    cardKey: card?.id ?? null,
  })
  const { reset } = swipe

  const run = useCallback(async (id, choice) => {
    const release = pinShellScroll()
    setBusy(true)
    setError('')
    setBack(null)
    if (!motionQuiet()) {
      setFly({ id, side: choice.side })
      await wait(FLY_MS)
    }
    let failure = ''
    let next = 'staff'
    try {
      const result = await sortDeed(id, choice.id)
      next = result?.next || 'staff'
    } catch (err) {
      failure = messageOf(err)
      reset()
    }
    await load()
    if (failure) setError(failure)
    else setFlash({ key: Date.now(), text: doneText(choice.id, next), undoId: id, side: choice.side })
    setFly(null)
    setBusy(false)
    release()
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
    const release = pinShellScroll()
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
    release()
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
            Здесь чужие наказания. Посмотрите доказательство и ответьте. Дальше карточку проверит один из сотрудников проекта, затем создатель.
          </p>
          <p className="deck-why">
            Каждую карточку берёт один из администраторов группы, после ответа её не видят остальные. Оплата за проверку появится, если создатель согласится с вашим ответом. Наказания которые выдали именно вы - проверяет кто-то другой, поэтому их здесь нет.
          </p>
          {!card && notes}
          {!queue && !error && <p className="staff-hint">Открываем наказания…</p>}
          {queue && !card && !error && waiting > 0 && (
            <p className="work-empty">Остальные карточки сейчас смотрят другие администраторы. Если они не ответят, карточки вернутся сюда.</p>
          )}
          {queue && !card && !error && waiting === 0 && (
            <p className="work-empty">Сейчас проверять нечего. Новые наказания коллег появятся здесь.</p>
          )}
          {card && (
            <p className="work-keys">
              Потяните карточку: вправо — подходит, влево — выдано неправильно, вниз — непонятно.
              {card.hasProof && card.proofMediaId ? ' Нажмите на фото, чтобы открыть его целиком.' : ''}
              <span className="deck-keys-only"> На клавиатуре: → подходит, ← выдано неправильно, ↓ непонятно, Ctrl+Z — вернуть ответ.</span>
            </p>
          )}
        </div>
        {card && (
          <div className="deck-col">
            <DeckCard
              card={card}
              band={BAND_LABEL[card.band] || 'Наказание'}
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
