import { useCallback, useEffect, useState } from 'react'
import CountUp from '../../../components/CountUp'
import { fetchStaffWork, isPanelPreviewMode, sortStaffDeed, unsortStaffDeed } from '../../../lib/adminClient'
import { VERDICT_BUTTON, waitCaption } from '../../../lib/deedSort'
import { playVerdictMeme } from '../../../lib/memeSounds'
import useSwipeDeck, { deckKey } from '../../../lib/useSwipeDeck'
import DeckCard, { DeckPileNote, FLY_MS, motionQuiet, pinShellScroll, useDeckLive, useRefill, useToastInView, useWarmProof, wait } from './DeckCard'

const CHOICES = [
  { id: 'wrong', label: VERDICT_BUTTON.wrong, stamp: 'Неправильно', hint: 'создатель увидит ваш ответ', side: 'left' },
  { id: 'weak', label: VERDICT_BUTTON.weak, stamp: 'Непонятно', hint: 'передать создателю', side: 'down' },
  { id: 'clear', label: VERDICT_BUTTON.clear, stamp: 'Подходит', hint: 'доказательство на месте', side: 'right' },
]

const BY_SIDE = { left: CHOICES[0], down: CHOICES[1], right: CHOICES[2] }
const STAMPS = CHOICES.map((choice) => ({ side: choice.side, label: choice.stamp }))

function adminStep(card) {
  return (card?.chain || []).find((step) => step.role === 'admin') || null
}

function doneText(choice, lift) {
  if (lift) return 'Заявка на разблокировку ушла создателю. Он снимет наказание или оставит его.'
  if (choice === 'clear') return 'Подходит. Создатель увидит ваш ответ и ответ администратора.'
  if (choice === 'wrong') return 'Наказание выдано неправильно. Создатель увидит это и решит сам. Заявку на снятие вы не подавали.'
  return 'Непонятно. Карточка ушла создателю. Другие сотрудники её уже не увидят.'
}

function messageOf(error) {
  return error?.message || 'Не удалось открыть проверку'
}

export default function StaffDesk({ onCount }) {
  const [queue, setQueue] = useState(null)
  const [error, setError] = useState('')
  const [flash, setFlash] = useState(null)
  const [busy, setBusy] = useState(false)
  const [fly, setFly] = useState(null)
  const [back, setBack] = useState(null)

  const load = useCallback(async () => {
    if (isPanelPreviewMode()) return
    try {
      const data = await fetchStaffWork()
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
  const pileNote = useDeckLive('staff', queue, setQueue, load)
  useWarmProof(queue?.nextProofMediaId)

  const card = queue?.card
  const prior = adminStep(card)
  const toastRef = useToastInView()
  const swipe = useSwipeDeck({
    onSwipe: (side) => choose(BY_SIDE[side], false),
    disabled: busy || Boolean(fly) || !card,
    cardKey: card?.id ?? null,
  })
  const { reset } = swipe

  const run = useCallback(async (id, choice, lift) => {
    const release = pinShellScroll()
    setBusy(true)
    setError('')
    setBack(null)
    if (!lift && !motionQuiet()) {
      setFly({ id, side: choice.side })
      await wait(FLY_MS)
    }
    let failure = ''
    try {
      await sortStaffDeed(id, choice?.id || 'wrong', lift)
    } catch (err) {
      failure = messageOf(err)
      reset()
    }
    await load()
    if (failure) setError(failure)
    else setFlash({ key: Date.now(), text: doneText(choice?.id, lift), undoId: id, side: choice?.side || 'left' })
    setFly(null)
    setBusy(false)
    release()
  }, [load, reset])

  const choose = useCallback((choice, lift = false) => {
    const id = card?.id
    if (!id || busy || fly) return false
    if (!lift && !choice) return false
    if (!lift) playVerdictMeme(choice.id)
    run(id, choice, lift)
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
      await unsortStaffDeed(last.undoId)
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
      if (choose(BY_SIDE[key], false)) event.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [choose, undo, flash])

  if (isPanelPreviewMode()) {
    return <p className="staff-hint">В копии панели наказания не проверяют. Это делается в настоящей панели.</p>
  }

  const locked = busy || Boolean(fly)
  const waiting = Number(queue?.waiting) || 0
  const flySide = fly && card && fly.id === card.id ? fly.side : ''
  const backSide = back && card && back.id === card.id ? back.side : ''
  const priorWrong = prior?.verdict === 'wrong'
  const band = prior
    ? `${prior.name}: ${(prior.label || '').toLowerCase()}`
    : 'Администратор не проверял'
  const note = priorWrong
    ? `${prior.name} проверил это наказание и указал, что оно выдано неправильно.`
    : prior?.verdict === 'weak'
      ? `${prior.name} не смог решить. Теперь решение за вами, затем за создателем.`
      : prior
        ? 'Сверьте доказательство с тем, что уже ответил администратор.'
        : 'Проверять администратору было некому. Вы первый, дальше карточку увидит создатель.'

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
          {pileNote && card && <DeckPileNote text={pileNote} />}
          <p className="deed-lead">
            Администратор группы уже посмотрел это наказание — его ответ на карточке. Проверьте, всё ли верно. Дальше карточку увидит создатель.
          </p>
          <p className="deck-why">
            Каждую карточку берёт один сотрудник, остальные её не видят. Оплата появится, если создатель согласится с вашим ответом.
          </p>
          {!card && notes}
          {!queue && !error && <p className="staff-hint">Открываем наказания…</p>}
          {queue && !card && !error && waiting > 0 && (
            <p className="work-empty">Остальные карточки сейчас смотрят другие сотрудники. Если они не ответят, карточки вернутся сюда.</p>
          )}
          {queue && !card && !error && waiting === 0 && (
            <p className="work-empty">Сейчас проверять нечего. Сюда приходят наказания, которые уже посмотрел администратор группы.</p>
          )}
          {card && (
            <p className="work-keys">
              Потяните карточку: вправо — подходит, влево — выдано неправильно, вниз — непонятно.
              {card.hasProof && card.proofMediaId ? ' Нажмите на фото, чтобы открыть его целиком.' : ''}
              <span className="deck-keys-only"> На клавиатуре те же стрелки. Ctrl+Z возвращает ответ.</span>
            </p>
          )}
        </div>
        {card && (
          <div className="deck-col">
            <DeckCard
              card={card}
              band={band}
              tone={prior?.verdict || ''}
              note={note}
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
                  onClick={() => choose(choice, false)}
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
            <div className={`lift-ask${priorWrong ? ' is-hot' : ''}`}>
              <button
                type="button"
                className="sec-btn sec-btn-ghost deck-btn is-ask"
                disabled={locked}
                onClick={() => choose(CHOICES[0], true)}
              >
                <span>Подать заявку на разблокировку</span>
                <small>
                  {priorWrong
                    ? 'администратор уже указал, что наказание выдано неправильно'
                    : 'если человек наказан зря. Создатель снимет наказание или отклонит заявку'}
                </small>
              </button>
            </div>
            {notes}
          </div>
        )}
      </div>
    </div>
  )
}
