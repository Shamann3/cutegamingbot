import { useCallback, useEffect, useRef, useState } from 'react'
import CountUp from '../../../components/CountUp'
import PhotoLook from '../../../components/PhotoLook'
import {
  dropDeed,
  fetchCreatorWork,
  fetchDeedDone,
  fetchDeedQueue,
  fetchDeedReviewers,
  isPanelPreviewMode,
  keepDeed,
  liftDeed,
  rejectLiftDeed,
  sortCreatorDeed,
  undoDeed,
} from '../../../lib/adminClient'
import { chainLine, chosenCredits, creditHint, openingOf, payLabel, people as peopleCount, SORT_LABEL, VERDICT_BUTTON, waitCaption } from '../../../lib/deedSort'
import { playVerdictMeme } from '../../../lib/memeSounds'
import useSwipeDeck, { deckKey } from '../../../lib/useSwipeDeck'
import DeckCard, { DeckPileNote, FLY_MS, motionQuiet, pinShellScroll, useDeckLive, useRefill, useToastInView, useWarmProof, wait, when } from './DeckCard'
import { DeedPayouts, DeedRates } from './DeedPay'
import PurseDesk from './PurseDesk'
import RateTune from './RateTune'

const STAMPS = [
  { side: 'right', label: 'В зарплату' },
  { side: 'left', label: 'Мимо' },
]

const KEEP_TEXT = 'В зарплату. Засчитано тем, у кого стояла галочка и чей ответ совпал.'
const DROP_TEXT = 'Мимо. Засчитаны проверки «неправильно», у которых стояла галочка. В архиве наказание осталось.'

function messageOf(error) {
  return error?.message || 'Не удалось открыть зарплаты'
}

export function CreatorDeck({ sorterId = 0, focusName = '', onCount, onDecided }) {
  const [queue, setQueue] = useState(null)
  const [error, setError] = useState('')
  const [flash, setFlash] = useState(null)
  const [busy, setBusy] = useState(false)
  const [fly, setFly] = useState(null)
  const [back, setBack] = useState(null)
  const [off, setOff] = useState(() => new Set())

  const load = useCallback(async () => {
    if (isPanelPreviewMode()) return
    try {
      const data = await fetchDeedQueue({ sorterId })
      setQueue(data)
      setError('')
      onCount?.(Number(data?.waiting) || 0)
    } catch (err) {
      setError(messageOf(err))
      onCount?.(0)
    }
  }, [sorterId, onCount])

  useEffect(() => {
    setFlash(null)
    setBack(null)
    setOff(new Set())
    load()
  }, [load])

  const card = queue?.card
  const toastRef = useToastInView()
  const watching = Boolean(card?.turn) && card.turn !== 'creator'
  const salaryOpen = Boolean(card) && !card.reviewStatus && !watching
  useRefill(queue, load)
  const pileNote = useDeckLive(sorterId ? '' : 'queue', queue, setQueue, load)
  useWarmProof(queue?.nextProofMediaId)
  const swipe = useSwipeDeck({
    onSwipe: (side) => decide(side === 'right' ? 'keep' : 'drop'),
    disabled: busy || Boolean(fly) || !salaryOpen,
    cardKey: card?.id ?? null,
  })
  const { reset } = swipe

  const run = useCallback(async (id, kind, credits, stays) => {
    const release = pinShellScroll()
    try {
      const side = kind === 'keep' ? 'right' : 'left'
      setBusy(true)
      setError('')
      setBack(null)
      if (!stays && !motionQuiet()) {
        setFly({ id, side })
        await wait(FLY_MS)
      }
      let failure = ''
      let liftOpen = false
      try {
        const result = kind === 'keep' ? await keepDeed(id, credits) : await dropDeed(id, credits)
        liftOpen = Boolean(result?.liftOpen)
      } catch (err) {
        failure = messageOf(err)
        reset()
      }
      await load()
      if (failure) setError(failure)
      else {
        const tail = liftOpen ? ' Осталась заявка на разблокировку.' : ''
        setFlash({ key: Date.now(), text: (kind === 'keep' ? KEEP_TEXT : DROP_TEXT) + tail, undoId: id, side, kind })
      }
      setFly(null)
      setBusy(false)
      if (!failure) onDecided?.()
    } finally {
      release()
    }
  }, [load, onDecided, reset])

  const decide = useCallback((kind) => {
    const id = card?.id
    if (!id || busy || fly || card.reviewStatus || (card.turn && card.turn !== 'creator')) return false
    run(id, kind, chosenCredits(card, kind, off), card.lift?.status === 'pending')
    return true
  }, [card, busy, fly, off, run])

  const undo = useCallback(async () => {
    const last = flash
    if (!last?.undoId || busy || fly) return
    const release = pinShellScroll()
    try {
      setBusy(true)
      setError('')
      let failure = ''
      try {
        await undoDeed(last.undoId)
        setBack({ id: last.undoId, side: last.side })
      } catch (err) {
        failure = messageOf(err)
      }
      await load()
      if (failure) {
        setError(failure)
        setFlash({ ...last, undoId: 0 })
      } else {
        setFlash({
          key: Date.now(),
          text: last.kind === 'keep'
            ? 'Решение отменено и убрано из зарплаты. Карточка снова перед вами.'
            : 'Решение отменено. Карточка снова перед вами.',
          undoId: 0,
        })
      }
      setBusy(false)
      if (!failure) onDecided?.()
    } finally {
      release()
    }
  }, [flash, busy, fly, load, onDecided])

  const settleLift = useCallback(async (kind) => {
    const id = card?.id
    if (!id || busy || fly) return
    setBusy(true)
    setError('')
    let failure = ''
    try {
      if (kind === 'lift') await liftDeed(id)
      else await rejectLiftDeed(id)
    } catch (err) {
      failure = messageOf(err)
    }
    await load()
    if (failure) setError(failure)
    else {
      setFlash({
        key: Date.now(),
        text: kind === 'lift'
          ? 'Наказание снято. Игроку отправлено сообщение, что после проверки его сняли.'
          : 'Заявка отклонена. Наказание остаётся.',
        undoId: 0,
      })
    }
    setBusy(false)
    if (!failure) onDecided?.()
  }, [card, busy, fly, load, onDecided])

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
      if (key === 'down') return
      if (decide(key === 'right' ? 'keep' : 'drop')) event.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [decide, undo, flash])

  if (isPanelPreviewMode()) {
    return <p className="staff-hint">В копии панели наказания не решают. Это делается в настоящей панели.</p>
  }

  const locked = busy || Boolean(fly)
  const waiting = Number(queue?.waiting) || 0
  const flySide = fly && card && fly.id === card.id ? fly.side : ''
  const backSide = back && card && back.id === card.id ? back.side : ''
  const label = card ? openingOf(card) : null
  const toggleCredit = (key) => {
    setOff((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

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
    <div className="tinder-wrap">
      <div className="deck-copy">
        {waiting > 0 && (
          <div className="deck-count">
            <CountUp className="deed-sum" value={waiting} />
            <span className="deck-count-cap">{waitCaption(waiting, 'вашего решения')}</span>
          </div>
        )}
        {pileNote && card && <DeckPileNote text={pileNote} />}
        <p className="deed-lead">
          {watching
            ? 'Эту карточку ещё не проверили. Она появится здесь, когда администратор группы или сотрудник проекта отправит ответ.'
            : focusName
              ? `Показаны только проверки: ${focusName}.`
              : 'Здесь только карточки, которые уже кто-то проверил. Пока её лишь открыли и могли забыть — её здесь нет. Второго ответа можно не ждать.'}
        </p>
        {!card && notes}
        {!queue && !error && <p className="staff-hint">Открываем наказания…</p>}
        {queue && !card && !error && (
          <p className="work-empty">
            {focusName
              ? 'Здесь пусто. Нажмите «Все, кто проверяет», чтобы увидеть остальные карточки.'
              : 'Сейчас решать нечего. Карточка появится, когда кто-то отправит ответ.'}
          </p>
        )}
      </div>
      {card && (
        <div className="deck-col">
          <DeckCard
            card={card}
            band={label.band}
            tone={label.tone}
            note={label.note}
            stamps={STAMPS}
            depth={Math.max(0, Math.min(2, waiting - 1))}
            fly={flySide}
            back={backSide}
            swipe={swipe}
          />
          <p className="tinder-hint deck-copy">
            {watching
              ? 'Зарплату решать рано. Кнопки появятся после ответа, и работа засчитается тому, кто проверил карточку.'
              : 'Галочка уже стоит. Вправо засчитает работу тому, кто сказал «подходит», и тому, кто выдал. Влево засчитает работу тому, кто сказал «неправильно». Снимите галочку, если этому человеку платить не нужно.'}
            {card.hasProof && card.proofMediaId ? ' Нажмите на фото, чтобы открыть его целиком.' : ''}
            {!watching && <span className="deck-keys-only"> На клавиатуре: → в зарплату, ← мимо, Ctrl+Z — вернуть решение.</span>}
          </p>
          {(card.credits || []).length > 0 && (
            <ul className="credit-list">
              {card.credits.map((person) => {
                const key = `${person.role}:${person.userId}`
                const never = person.payable === 'never'
                const on = !never && !off.has(key)
                return (
                  <li key={key} className={never ? 'is-never' : ''}>
                    <label>
                      {never ? (
                        <i className="credit-dot" aria-hidden="true" />
                      ) : (
                        <input
                          type="checkbox"
                          checked={on}
                          disabled={locked || !salaryOpen}
                          onChange={() => toggleCredit(key)}
                        />
                      )}
                      <span>
                        <strong>{person.name}</strong>
                        <small>{creditHint(person)}</small>
                      </span>
                    </label>
                  </li>
                )
              })}
            </ul>
          )}
          {card.lift?.status === 'pending' && (
            <div className="lift-box">
              <p>
                {card.lift.by} просит снять это наказание. Снятие и зарплата решаются отдельно: влево наказание не снимает.
                {card.lift.canLift
                  ? ' «Разблокировать» снимет ровно то, что выдали, и напишет игроку.'
                  : ''}
              </p>
              {card.lift.blocked && <p className="lift-block">{card.lift.blocked}</p>}
              <div className="deed-choice tinder-choice">
                <button
                  type="button"
                  className="sec-btn sec-btn-ghost deck-btn is-wrong"
                  disabled={locked}
                  onClick={() => settleLift('reject')}
                >
                  <span>Отклонить заявку</span>
                  <small>наказание останется</small>
                </button>
                {card.lift.canLift && (
                  <button
                    type="button"
                    className="sec-btn sec-btn-ghost deck-btn is-clear"
                    disabled={locked}
                    onClick={() => settleLift('lift')}
                  >
                    <span>Разблокировать</span>
                    <small>снять и написать игроку</small>
                  </button>
                )}
              </div>
            </div>
          )}
          {salaryOpen ? (
            <div className="deed-choice tinder-choice">
              <button type="button" className="sec-btn sec-btn-ghost deck-btn is-wrong deed-no" disabled={locked} onClick={() => decide('drop')}>
                <span><span className="deck-arrow" aria-hidden="true">←</span>Мимо</span>
                <small>тем, кто сказал «неправильно»</small>
              </button>
              <button type="button" className="sec-btn sec-btn-ghost deck-btn is-clear deed-yes" disabled={locked} onClick={() => decide('keep')}>
                <span>В зарплату<span className="deck-arrow" aria-hidden="true">→</span></span>
                <small>тому, кто выдал, и кто сказал «подходит»</small>
              </button>
            </div>
          ) : card.reviewStatus ? (
            <p className="deck-note deck-copy">
              Зарплата уже решена: {card.reviewStatus === 'kept' ? 'в зарплату' : 'мимо'}.
            </p>
          ) : (
            <p className="deck-note deck-copy">
              Кнопки появятся, когда администратор группы или сотрудник проекта отправит ответ. Тогда работа засчитается ему.
            </p>
          )}
          {notes}
        </div>
      )}
    </div>
  )
}

const SELF_CHOICES = [
  { id: 'wrong', label: VERDICT_BUTTON.wrong, stamp: 'Неправильно', hint: 'в зарплату никого', side: 'left' },
  { id: 'weak', label: VERDICT_BUTTON.weak, stamp: 'Непонятно', hint: 'закрыть без оплаты', side: 'down' },
  { id: 'clear', label: VERDICT_BUTTON.clear, stamp: 'В зарплату', hint: 'тому, кто выдал', side: 'right' },
]

const SELF_BY_SIDE = { left: SELF_CHOICES[0], down: SELF_CHOICES[1], right: SELF_CHOICES[2] }
const SELF_STAMPS = SELF_CHOICES.map((choice) => ({ side: choice.side, label: choice.stamp }))

function selfText(choice, paid) {
  if (choice === 'clear' && paid) return 'Подходит. Сразу в зарплату тому, кто выдал — администратор это или сотрудник, роли не важны.'
  if (choice === 'clear') return 'Подходит. В архиве нет того, кто выдал, поэтому в зарплату отправить некого.'
  if (choice === 'wrong') return 'Наказание выдано неправильно. В зарплату никого не отправил, в архиве оно осталось.'
  return 'Непонятно. Карточка закрыта, в зарплату никого не отправил.'
}

export function CreatorSelf() {
  const [queue, setQueue] = useState(null)
  const [error, setError] = useState('')
  const [flash, setFlash] = useState(null)
  const [busy, setBusy] = useState(false)
  const [fly, setFly] = useState(null)
  const [back, setBack] = useState(null)

  const load = useCallback(async () => {
    if (isPanelPreviewMode()) return
    try {
      const data = await fetchCreatorWork()
      setQueue(data)
      setError('')
    } catch (err) {
      setError(messageOf(err))
    }
  }, [])

  useEffect(() => { load() }, [load])
  useRefill(queue, load)
  const pileNote = useDeckLive('own', queue, setQueue, load)
  useWarmProof(queue?.nextProofMediaId)

  const card = queue?.card
  const toastRef = useToastInView()
  const swipe = useSwipeDeck({
    onSwipe: (side) => choose(SELF_BY_SIDE[side]),
    disabled: busy || Boolean(fly) || !card,
    cardKey: card?.id ?? null,
  })
  const { reset } = swipe

  const run = useCallback(async (id, choice) => {
    const release = pinShellScroll()
    try {
      setBusy(true)
      setError('')
      setBack(null)
      if (!motionQuiet()) {
        setFly({ id, side: choice.side })
        await wait(FLY_MS)
      }
      let failure = ''
      let paid = false
      try {
        const result = await sortCreatorDeed(id, choice.id)
        paid = Boolean(result?.paid)
      } catch (err) {
        failure = messageOf(err)
        reset()
      }
      await load()
      if (failure) setError(failure)
      else setFlash({ key: Date.now(), text: selfText(choice.id, paid), undoId: id, side: choice.side })
      setFly(null)
      setBusy(false)
    } finally {
      release()
    }
  }, [load, reset])

  const choose = useCallback((choice) => {
    const id = card?.id
    if (!id || busy || fly || !choice) return false
    playVerdictMeme(choice.id)
    run(id, choice)
    return true
  }, [card, busy, fly, run])

  const undo = useCallback(async () => {
    const last = flash
    if (!last?.undoId || busy || fly) return
    const release = pinShellScroll()
    try {
      setBusy(true)
      setError('')
      let failure = ''
      try {
        await undoDeed(last.undoId)
        setBack({ id: last.undoId, side: last.side })
      } catch (err) {
        failure = messageOf(err)
      }
      await load()
      if (failure) {
        setError(failure)
        setFlash({ ...last, undoId: 0 })
      } else {
        setFlash({ key: Date.now(), text: 'Ответ отменён и убран из зарплаты. Карточка снова перед вами.', undoId: 0 })
      }
      setBusy(false)
    } finally {
      release()
    }
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
      if (choose(SELF_BY_SIDE[key])) event.preventDefault()
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
            Эти наказания ещё никто не разбирал. Ваш ответ забирает карточку у администраторов и сотрудников и сразу решает зарплату.
          </p>
          <p className="deck-why">
            «Подходит» засчитывает тому, кто выдал — администратору группы или сотруднику проекта, это одно и то же. «Неправильно» и «непонятно» никого не оплачивают.
          </p>
          {!card && notes}
          {!queue && !error && <p className="staff-hint">Открываем наказания…</p>}
          {queue && !card && !error && waiting > 0 && (
            <p className="work-empty">Остальные карточки сейчас смотрят. Если ответа не будет, они вернутся сюда.</p>
          )}
          {queue && !card && !error && waiting === 0 && (
            <p className="work-empty">Сейчас проверять нечего. Сюда приходят наказания, которые ещё не открыл администратор или сотрудник.</p>
          )}
          {card && (
            <p className="work-keys">
              Потяните карточку: вправо — в зарплату, влево — выдано неправильно, вниз — непонятно.
              {card.hasProof && card.proofMediaId ? ' Нажмите на фото, чтобы открыть его целиком.' : ''}
              <span className="deck-keys-only"> На клавиатуре те же стрелки. Ctrl+Z возвращает ответ.</span>
            </p>
          )}
        </div>
        {card && (
          <div className="deck-col">
            <DeckCard
              card={card}
              band="Ещё никто не проверял"
              note="Ответ сразу уходит в зарплату того, кто выдал наказание."
              stamps={SELF_STAMPS}
              depth={Math.max(0, Math.min(2, waiting - 1))}
              fly={flySide}
              back={backSide}
              swipe={swipe}
            />
            <div className="work-choice">
              {SELF_CHOICES.map((choice) => (
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

function Bar({ person, delay }) {
  const parts = [
    { id: 'clear', value: person.clear },
    { id: 'wrong', value: person.wrong },
    { id: 'weak', value: person.weak },
  ].filter((part) => part.value > 0)
  if (!parts.length) return <span className="pay-bar is-empty" aria-hidden="true" />
  return (
    <span className="pay-bar" aria-hidden="true">
      {parts.map((part, index) => (
        <i
          key={part.id}
          className={`is-${part.id}`}
          style={{ '--part': part.value, animationDelay: `${delay + index * 90}ms` }}
        />
      ))}
    </span>
  )
}

function Legend({ person }) {
  return (
    <span className="pay-legend">
      <span><i className="is-clear" aria-hidden="true" />{SORT_LABEL.clear} {person.clear || 0}</span>
      <span><i className="is-wrong" aria-hidden="true" />{SORT_LABEL.wrong} {person.wrong || 0}</span>
      <span><i className="is-weak" aria-hidden="true" />{SORT_LABEL.weak} {person.weak || 0}</span>
    </span>
  )
}

function Fate({ person }) {
  return (
    <span className="pay-fate">
      В зарплату {person.kept || 0} · мимо {person.dropped || 0} · ждут вас {person.waiting || 0}
    </span>
  )
}

function People({ people, totals, sorterId, onPick }) {
  const listRef = useRef(null)

  useEffect(() => {
    if (listRef.current) listRef.current.scrollLeft = 0
  }, [])

  return (
    <div ref={listRef} className="pay-people" aria-label="Кто сколько проверил">
      <button
        type="button"
        className={`pay-person${!sorterId ? ' is-on' : ''}`}
        aria-pressed={!sorterId}
        onClick={() => onPick(0, '')}
      >
        <CountUp className="pay-person-count" value={totals?.reviewed || 0} />
        <span className="pay-person-label">проверок всего</span>
        <strong>Все, кто проверяет</strong>
        <span className="pay-person-title">В списке {peopleCount(totals?.admins || 0)}</span>
        <Bar person={totals || {}} delay={120} />
        <Legend person={totals || {}} />
        <Fate person={totals || {}} />
      </button>
      {people.map((person, index) => {
        const delay = Math.min(index + 1, 12) * 45
        return (
          <button
            key={person.id}
            type="button"
            className={`pay-person${sorterId === person.id ? ' is-on' : ''}`}
            aria-pressed={sorterId === person.id}
            style={{ animationDelay: `${delay}ms` }}
            onClick={() => onPick(person.id, person.name)}
          >
            <CountUp className="pay-person-count" value={person.reviewed} />
            <span className="pay-person-label">проверок</span>
            <strong>{person.name}</strong>
            {person.title && <span className="pay-person-title">{person.title}</span>}
            {person.reviewed ? (
              <>
                <Bar person={person} delay={delay + 120} />
                <Legend person={person} />
                <Fate person={person} />
                {person.lastAt && <span className="pay-person-when">Последняя проверка {when(person.lastAt)}</span>}
              </>
            ) : (
              <span className="pay-person-when">Проверок пока нет.</span>
            )}
          </button>
        )
      })}
    </div>
  )
}

const DONE_FILTERS = [
  { id: '', label: 'Все' },
  { id: 'kept', label: 'В зарплате' },
  { id: 'dropped', label: 'Не в зарплате' },
]

function DoneList({ sorterId, focusName, tick }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')

  const load = useCallback(async () => {
    if (isPanelPreviewMode()) return
    try {
      const data = await fetchDeedDone({ sorterId, status })
      setItems(data?.items || [])
      setError('')
    } catch (err) {
      setError(messageOf(err))
    }
  }, [sorterId, status])

  useEffect(() => { load() }, [load, tick])

  return (
    <div className="done-desk">
      <p className="deed-lead deck-copy">
        {focusName
          ? `Решения по проверкам: ${focusName}. Новые сверху.`
          : 'Последние 40 решений, новые сверху.'}
      </p>
      <div className="deed-filters">
        {DONE_FILTERS.map((item) => (
          <button
            key={item.id || 'all'}
            type="button"
            className={`sec-btn${status === item.id ? '' : ' sec-btn-ghost'}`}
            aria-pressed={status === item.id}
            onClick={() => setStatus(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {error && <p className="staff-hint deck-copy" role="alert">{error}</p>}
      {!items && !error && <p className="staff-hint deck-copy">Открываем решения…</p>}
      {items && !items.length && !error && <p className="work-empty deck-copy">Здесь пока пусто.</p>}
      {items?.length > 0 && (
        <div className="done-list">
          {items.map((item, index) => (
            <article
              key={item.id}
              className={`staff-member-row done-row is-${item.status}${item.hasProof && item.proofMediaId ? ' has-photo' : ''}`}
              style={{ animationDelay: `${Math.min(index, 10) * 35}ms` }}
            >
              {item.hasProof && item.proofMediaId && (
                <PhotoLook fileId={item.proofMediaId} alt="Фото доказательства" className="is-mini" />
              )}
              <div className="done-copy">
                <span className="done-mark">{payLabel(item.status)}</span>
                <h4 className="staff-card-name">{item.actionLabel} · {item.targetName || 'игрок'}</h4>
                <p className="staff-card-date">
                  Выдал {item.adminName || 'администратор'} · {when(item.createdAt)}
                </p>
                <p className="staff-card-date">
                  {chainLine(item)} · решено {when(item.reviewedAt)}
                </p>
                {item.reason && <p className="done-reason">{item.reason}</p>}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}

export default function CreatorPay({ showPayroll = false, payroll = null }) {
  const [view, setView] = useState('check')
  const [roster, setRoster] = useState(null)
  const [error, setError] = useState('')
  const [sorterId, setSorterId] = useState(0)
  const [focusName, setFocusName] = useState('')
  const [tick, setTick] = useState(0)
  const preview = isPanelPreviewMode()

  const load = useCallback(async () => {
    if (isPanelPreviewMode()) return
    try {
      setRoster(await fetchDeedReviewers())
      setError('')
    } catch (err) {
      setError(messageOf(err))
    }
  }, [])

  useEffect(() => { load() }, [load, tick])

  const decided = useCallback(() => setTick((value) => value + 1), [])

  const pick = (id, name) => {
    setSorterId(id)
    setFocusName(id ? name : '')
  }

  const views = [
    { id: 'check', label: 'Проверка' },
    { id: 'self', label: 'Сами' },
    { id: 'done', label: 'Решённые' },
    { id: 'rates', label: 'Нормы' },
    { id: 'cash', label: 'Касса' },
    { id: 'payouts', label: 'К выплате' },
  ]
  if (showPayroll) views.push({ id: 'payroll', label: 'Оклады' })

  const lens = view === 'check' || view === 'done'

  return (
    <div className="pay-desk">
      <nav className="sec-tabs deed-views" aria-label="Зарплаты">
        {views.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`sec-tab${view === item.id ? ' sec-tab-active' : ''}`}
            onClick={() => setView(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      {!preview && view !== 'cash' && view !== 'rates' && view !== 'payroll' && <RateTune compact />}

      {lens && preview && <p className="staff-hint deck-copy">В копии панели чужие проверки не открываются.</p>}
      {view === 'self' && preview && <p className="staff-hint deck-copy">В копии панели наказания не проверяют.</p>}
      {view === 'self' && !preview && (
        <div className="pay-lens" key="self">
          <CreatorSelf />
        </div>
      )}

      {lens && !preview && (
        <>
          <div className="deck-copy">
            <p className="deed-lead">
              Сюда приходит карточка только после ответа. Ваше решение засчитает работу тому, кто её проверил: вправо — «подходит» и тому, кто выдал, влево — «неправильно».
            </p>
            <p className="deck-why">
              Нажмите на человека, чтобы смотреть только его проверки. Пока ответа нет, карточка у администратора или сотрудника и здесь не показывается.
            </p>
          </div>
          {error && <p className="staff-hint deck-copy" role="alert">{error}</p>}
          {!roster && !error && <p className="staff-hint deck-copy">Считаем проверки…</p>}
          {roster && !roster.people?.length && (
            <p className="work-empty deck-copy">
              Проверять пока некому. Администраторам групп нужно право «Архив» в разделе
              «Стафф → Администраторы → Должности» — у них появится вкладка «Работа» рядом с «Главная».
              Сотрудники проекта проверяют во вкладке «Работа» рядом с «Игроки» и «Архив».
              Наказания, которые ещё никто не открыл, лежат во вкладке «Сами».
            </p>
          )}
          <div className="pay-check">
            {roster?.people?.length > 0 && (
              <People people={roster.people} totals={roster.totals} sorterId={sorterId} onPick={pick} />
            )}
            <div className="pay-lens" key={view}>
              {view === 'check'
                ? <CreatorDeck sorterId={sorterId} focusName={focusName} onDecided={decided} />
                : <DoneList sorterId={sorterId} focusName={focusName} tick={tick} />}
            </div>
          </div>
        </>
      )}
      {view === 'rates' && <DeedRates />}
      {view === 'cash' && <PurseDesk />}
      {view === 'payouts' && <DeedPayouts />}
      {view === 'payroll' && showPayroll && payroll}
    </div>
  )
}
