import { useCallback, useEffect, useRef, useState } from 'react'
import CountUp from '../../../components/CountUp'
import PhotoLook from '../../../components/PhotoLook'
import {
  dropDeed,
  fetchDeedDone,
  fetchDeedQueue,
  fetchDeedReviewers,
  isPanelPreviewMode,
  keepDeed,
  undoDeed,
} from '../../../lib/adminClient'
import { SORT_LABEL, admins, checkedBy, payLabel, waitCaption } from '../../../lib/deedSort'
import useSwipeDeck, { deckKey } from '../../../lib/useSwipeDeck'
import DeckCard, { FLY_MS, motionQuiet, useToastInView, wait, when } from './DeckCard'
import { DeedPayouts, DeedRates } from './DeedPay'

const STAMPS = [
  { side: 'right', label: 'В зарплату' },
  { side: 'left', label: 'Мимо' },
]

const KEEP_TEXT = 'В зарплату. Засчитано тому, кто выдал наказание.'
const DROP_TEXT = 'Мимо. В зарплату не пошло, в архиве наказание осталось.'

function messageOf(error) {
  return error?.message || 'Не удалось открыть зарплаты'
}

function bandOf(card) {
  const names = (card.unclearNames || []).filter(Boolean)
  if (card.sortVerdict === 'clear' || card.sortVerdict === 'wrong') {
    return {
      band: `${card.sorterName || 'Администратор'}: ${SORT_LABEL[card.sortVerdict].toLowerCase()}`,
      tone: card.sortVerdict,
      note: names.length ? `До этого не смогли решить: ${names.join(', ')}` : '',
    }
  }
  if (card.sortVerdict === 'weak') {
    return {
      band: names.length ? `Не смогли решить: ${names.join(', ')}` : 'Не смогли решить',
      tone: 'weak',
      note: 'Пока оно ждёт вас, его могут проверить и другие администраторы.',
    }
  }
  return { band: 'Некому было проверить', tone: '', note: 'Решение сразу за вами.' }
}

export function CreatorDeck({ sorterId = 0, focusName = '', onCount, onDecided }) {
  const [queue, setQueue] = useState(null)
  const [error, setError] = useState('')
  const [flash, setFlash] = useState(null)
  const [busy, setBusy] = useState(false)
  const [fly, setFly] = useState(null)
  const [back, setBack] = useState(null)

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
    load()
  }, [load])

  const card = queue?.card
  const toastRef = useToastInView(flash?.key)
  const swipe = useSwipeDeck({
    onSwipe: (side) => decide(side === 'right' ? 'keep' : 'drop'),
    disabled: busy || Boolean(fly) || !card,
    cardKey: card?.id ?? null,
  })
  const { reset } = swipe

  const run = useCallback(async (id, kind) => {
    const side = kind === 'keep' ? 'right' : 'left'
    setBusy(true)
    setError('')
    setBack(null)
    if (!motionQuiet()) {
      setFly({ id, side })
      await wait(FLY_MS)
    }
    let failure = ''
    try {
      if (kind === 'keep') await keepDeed(id)
      else await dropDeed(id)
    } catch (err) {
      failure = messageOf(err)
      reset()
    }
    await load()
    if (failure) setError(failure)
    else setFlash({ key: Date.now(), text: kind === 'keep' ? KEEP_TEXT : DROP_TEXT, undoId: id, side, kind })
    setFly(null)
    setBusy(false)
    if (!failure) onDecided?.()
  }, [load, onDecided, reset])

  const decide = useCallback((kind) => {
    const id = card?.id
    if (!id || busy || fly) return false
    run(id, kind)
    return true
  }, [card, busy, fly, run])

  const undo = useCallback(async () => {
    const last = flash
    if (!last?.undoId || busy || fly) return
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
  }, [flash, busy, fly, load, onDecided])

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
  const label = card ? bandOf(card) : null

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
        <p className="deed-lead">
          {focusName
            ? `Показаны только проверки: ${focusName}.`
            : 'Сначала идут наказания с ответом «подходит», затем «не подходит», затем «непонятно», в конце — те, что некому было проверить.'}
        </p>
        {!card && notes}
        {!queue && !error && <p className="staff-hint">Открываем наказания…</p>}
        {queue && !card && !error && (
          <p className="work-empty">
            {focusName ? 'Здесь пусто. Нажмите «Все администраторы», чтобы увидеть остальные проверки.' : 'Сейчас решать нечего.'}
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
            Потяните карточку: вправо — в зарплату, влево — мимо.
            {card.hasProof && card.proofMediaId ? ' Нажмите на фото, чтобы открыть его целиком.' : ''}
            <span className="deck-keys-only"> На клавиатуре: → в зарплату, ← мимо, Ctrl+Z — вернуть решение.</span>
          </p>
          <div className="deed-choice tinder-choice">
            <button type="button" className="sec-btn sec-btn-ghost deck-btn is-wrong deed-no" disabled={locked} onClick={() => decide('drop')}>
              <span><span className="deck-arrow" aria-hidden="true">←</span>Мимо</span>
              <small>в зарплату не пойдёт</small>
            </button>
            <button type="button" className="sec-btn sec-btn-ghost deck-btn is-clear deed-yes" disabled={locked} onClick={() => decide('keep')}>
              <span>В зарплату<span className="deck-arrow" aria-hidden="true">→</span></span>
              <small>тому, кто выдал наказание</small>
            </button>
          </div>
          {notes}
        </div>
      )}
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
        <strong>Все администраторы</strong>
        <span className="pay-person-title">В списке {admins(totals?.admins || 0)}</span>
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
                  {checkedBy(item)} · решено {when(item.reviewedAt)}
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
    { id: 'done', label: 'Решённые' },
    { id: 'rates', label: 'Нормы' },
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

      {lens && preview && <p className="staff-hint deck-copy">В копии панели чужие проверки не открываются.</p>}

      {lens && !preview && (
        <>
          <div className="deck-copy">
            <p className="deed-lead">
              Администраторы заранее проверяют чужие наказания, поэтому к вам они приходят с готовым ответом — остаётся решить одним жестом.
            </p>
            <p className="deck-why">
              Нажмите на человека, чтобы смотреть только его проверки. В зарплату идёт только то, что вы отправили вправо.
            </p>
          </div>
          {error && <p className="staff-hint deck-copy" role="alert">{error}</p>}
          {!roster && !error && <p className="staff-hint deck-copy">Считаем проверки…</p>}
          {roster && !roster.people?.length && (
            <p className="work-empty deck-copy">
              Проверять чужие наказания пока некому. Включите должности право «Архив» в разделе
              «Стафф → Администраторы → Должности» — у этих людей появится вкладка «Работа», и наказания
              начнут приходить к вам уже проверенными.
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
      {view === 'payouts' && <DeedPayouts />}
      {view === 'payroll' && showPayroll && payroll}
    </div>
  )
}
