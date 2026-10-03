import { useCallback, useEffect, useMemo, useState } from 'react'
import TgPhoto from '../../../components/TgPhoto'
import {
  collectDeedRates,
  dropDeed,
  fetchDeedDone,
  fetchDeedMine,
  fetchDeedPayouts,
  fetchDeedQueue,
  fetchDeedRates,
  isPanelPreviewMode,
  keepDeed,
  payDeed,
  saveDeedRates,
} from '../../../lib/adminClient'

const SORTS = [
  { id: 'new', label: 'Сначала новые' },
  { id: 'old', label: 'Сначала старые' },
  { id: 'admin', label: 'По администратору' },
  { id: 'action', label: 'По наказанию' },
]

const ACTIONS = [
  { id: '', label: 'Все' },
  { id: 'ban', label: 'Баны' },
  { id: 'mute', label: 'Муты' },
  { id: 'kick', label: 'Кики' },
  { id: 'warn', label: 'Предупреждения' },
]

const COUNTS = {
  Баны: ['бан', 'бана', 'банов'],
  Муты: ['мут', 'мута', 'мутов'],
  Кики: ['кик', 'кика', 'киков'],
  Предупреждения: ['предупреждение', 'предупреждения', 'предупреждений'],
}

function money(value) {
  return `${Number(value || 0).toLocaleString('ru-RU')} кут`
}

function countPhrase(n, title) {
  const num = Number(n) || 0
  const forms = COUNTS[title]
  if (!forms) return `${num} дел «${title}»`
  const n10 = num % 10
  const n100 = num % 100
  let form = forms[2]
  if (n10 === 1 && n100 !== 11) form = forms[0]
  else if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) form = forms[1]
  return `${num} ${form}`
}

function when(iso) {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

function duration(minutes) {
  if (minutes == null) return 'срок не указан'
  if (minutes >= 60 * 24 * 365) return 'навсегда'
  if (minutes >= 60 * 24) return `${Math.round(minutes / (60 * 24))} дн.`
  if (minutes >= 60) return `${Math.round(minutes / 60)} ч.`
  return `${minutes} мин.`
}

function nearest(lines) {
  const open = (lines || []).filter((line) => line.enabled && line.everyN > 0 && line.rewardKut > 0 && line.left > 0)
  open.sort((a, b) => a.left - b.left || b.rewardKut - a.rewardKut)
  return open[0] || null
}

function messageOf(error) {
  return error?.message || 'Не удалось загрузить'
}

function motionQuiet() {
  if (typeof window === 'undefined') return true
  if (document.body.classList.contains('perf-light')) return true
  return Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)
}

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function DeedPayouts() {
  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(0)

  const load = useCallback(async () => {
    if (isPanelPreviewMode()) return
    try {
      const data = await fetchDeedPayouts()
      setItems(data.items || [])
      setError('')
    } catch (err) {
      const text = messageOf(err)
      setError(text.includes('создатель') ? '' : text)
      setItems([])
    }
  }, [])

  useEffect(() => { load() }, [load])

  const pay = async (id) => {
    setBusyId(id)
    setError('')
    try {
      await payDeed(id)
      await load()
    } catch (err) {
      setError(messageOf(err))
    } finally {
      setBusyId(0)
    }
  }

  const owed = items.filter((item) => item.status === 'owed')
  if (!owed.length && !error) return null
  return (
    <div className="deed-lines">
      <h3 className="staff-punish-title">К выплате</h3>
      {error && <p className="staff-hint">{error}</p>}
      {owed.map((item) => (
        <article key={item.id} className="staff-member-row">
          <div className="staff-member-info">
            <span className="staff-card-name">{item.adminName} · {money(item.rewardKut)}</span>
            <span className="staff-card-date">
              {item.actionLabel}, норма {item.milestone}
              {item.purse === 'manual' ? ' · платите сами' : ' · кут с технических групп'}
            </span>
          </div>
          <button type="button" className="sec-btn" disabled={busyId === item.id} onClick={() => pay(item.id)}>
            {busyId === item.id ? 'Списываем…' : item.purse === 'manual' ? 'Отметить выплату' : 'Выплатить'}
          </button>
        </article>
      ))}
    </div>
  )
}

export function DeedMine({ isProjectCreator = false }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    if (isPanelPreviewMode()) return
    setError('')
    try {
      setData(await fetchDeedMine())
    } catch (err) {
      setError(messageOf(err))
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  if (isPanelPreviewMode()) {
    return (
      <p className="staff-hint">
        В копии панели чужая зарплата не открывается. Свои куты видны в настоящем кабинете.
      </p>
    )
  }

  if (!data) {
    return <p className="staff-hint">{error || 'Считаем подтверждённые дела…'}</p>
  }

  const lines = data?.lines || []
  const next = nearest(lines)
  const owed = data?.owedKut || 0

  return (
    <div className="deed-mine">
      <p className="deed-sum">{money(owed)}</p>
      <p className="deed-lead">
        {owed > 0
          ? 'Эта сумма уже набрана. Создатель отпускает выплату, и кут приходит из технических групп.'
          : next
            ? `Ещё ${countPhrase(next.left, next.title)} — и ${money(next.rewardKut)}. Каждое дело создатель смотрит сам.`
            : 'Когда создатель включит оплату за наказания и поставит сумму, здесь будет видно, сколько кут даёт каждое действие.'}
      </p>
      {error && <p className="staff-hint">{error}</p>}
      <div className="deed-facts">
        <span>На проверке: {data?.waiting ?? '…'}</span>
        <span>Не засчитано: {data?.dropped ?? '…'}</span>
        <span>Уже получено: {money(data?.paidKut || 0)}</span>
      </div>
      <div className="deed-lines">
        {lines.map((line) => {
          const width = line.everyN > 0 ? Math.min(100, Math.round((line.into / line.everyN) * 100)) : 0
          return (
            <article key={line.actionType} className="staff-member-row deed-line">
              <div className="staff-member-info">
                <span className="staff-card-name">{line.title}</span>
                <span className="staff-card-date">
                  {line.confirmed} подтверждено · каждые {line.everyN} = {money(line.rewardKut)}
                  {line.purse === 'manual' ? ' · выплачивает создатель' : ' · кут с технических групп'}
                </span>
              </div>
              <div className="deed-bar" aria-hidden="true"><span style={{ width: `${width}%` }} /></div>
              <p className="staff-answer-a">
                {line.rewardKut > 0 && line.left > 0
                  ? `До ${money(line.rewardKut)} осталось ${countPhrase(line.left, line.title)}.`
                  : line.rewardKut > 0
                    ? 'Норма набрана, выплата ждёт создателя.'
                    : 'Сумма не поставлена: дела можно разбирать, выплата не откроется.'}
              </p>
            </article>
          )
        })}
      </div>
      {isProjectCreator && <DeedPayouts />}
      {(data?.payouts || []).length > 0 && (
        <div className="deed-lines">
          {data.payouts.map((item) => (
            <article key={item.id} className="staff-member-row">
              <div className="staff-member-info">
                <span className="staff-card-name">{item.actionLabel} · {money(item.rewardKut)}</span>
                <span className="staff-card-date">
                  {item.status === 'paid' ? `Выплачено ${when(item.paidAt)}` : 'Ждёт, пока создатель отпустит выплату'}
                  {item.note ? ` · ${item.note}` : ''}
                </span>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}

function DeedCard({ card, leaving = '' }) {
  const place = [card.chatTitle, card.scopeLabel].filter(Boolean).join(' · ')
  const motion = leaving === 'left' ? ' is-out-left' : leaving === 'right' ? ' is-out-right' : ''
  return (
    <article key={card.id} className={`staff-member-row deed-card${motion}`}>
      <div className="deed-face">
        {card.hasProof && card.proofMediaId
          ? <TgPhoto fileId={card.proofMediaId} className="deed-photo" />
          : card.targetPhoto
            ? <img className="deed-photo" src={card.targetPhoto} alt="" />
            : (
              <div className="deed-photo deed-photo-empty">
                <strong>{card.actionLabel}</strong>
                <span>{card.reason || 'Причина в архиве не записана'}</span>
              </div>
            )}
      </div>
      <div className="deed-copy">
        <h3 className="staff-card-name">{card.actionLabel} · {card.targetName || 'игрок'}</h3>
        <p className="staff-card-date">
          {card.adminName || 'администратор'} · {when(card.createdAt)} · {duration(card.durationMinutes)}
          {place ? ` · ${place}` : ''}
        </p>
        <p className="deed-reason">{card.reason || 'Причина в архиве не записана'}</p>
        {card.evidence && <p className="staff-answer-a">Доказательство: {card.evidence}</p>}
        <p className="staff-answer-a">
          В архиве этого игрока {card.archiveCount} записей.
          {card.rateEnabled && card.everyN > 0
            ? ` Это одно дело к норме «${card.rateTitle}»: ${card.everyN} подтверждённых = ${money(card.rewardKut)}.`
            : ' Для этого типа норма ещё выключена: дело можно разобрать, в выплату оно не войдёт.'}
        </p>
        {card.history?.length > 0 && (
          <ul className="deed-history">
            {card.history.map((item) => (
              <li key={item.id}>
                <span>{item.actionLabel}</span>
                <span>{item.reason || 'без причины'}</span>
                <span>{item.adminName}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </article>
  )
}

function DeedRates() {
  const [items, setItems] = useState([])
  const [ready, setReady] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState('')

  const load = useCallback(async () => {
    setError('')
    try {
      const data = await fetchDeedRates()
      setItems(data.items || [])
      setReady(true)
    } catch (err) {
      setError(messageOf(err))
    }
  }, [])

  useEffect(() => { load() }, [load])

  const patch = (actionType, field, value) => {
    setItems((prev) => prev.map((item) => (item.actionType === actionType ? { ...item, [field]: value } : item)))
  }

  const save = async () => {
    setBusy('save')
    setError('')
    setNotice('')
    try {
      const clean = items.map((item) => ({
        ...item,
        everyN: Math.max(1, Number(item.everyN) || 1),
        rewardKut: Math.max(0, Number(item.rewardKut) || 0),
      }))
      const data = await saveDeedRates(clean)
      setItems(data.items || [])
      setNotice('Нормы сохранены. Уже подтверждённые дела пересчитаны.')
    } catch (err) {
      setError(messageOf(err))
    } finally {
      setBusy('')
    }
  }

  const collect = async () => {
    setBusy('collect')
    setError('')
    setNotice('')
    try {
      const data = await collectDeedRates()
      setItems(data.items || [])
      setReady(true)
      setNotice(data.added?.length
        ? `Добавлены выключенные задания: ${data.added.map((item) => item.title).join(', ')}. Включите их и поставьте сумму.`
        : 'Новых типов в архиве за 90 дней нет. Текущие задания на месте.')
    } catch (err) {
      setError(messageOf(err))
    } finally {
      setBusy('')
    }
  }

  return (
    <div className="deed-rates">
      <p className="deed-lead">
        Задание платит, только когда вы его включили и поставили число. Сбор смотрит архив и предлагает типы, которые администраторы уже делают. Сам он сумму не включает.
      </p>
      {error && <p className="staff-hint">{error}</p>}
      {notice && <p className="staff-hint">{notice}</p>}
      {!ready && !error && <p className="staff-hint">Открываем нормы…</p>}
      {ready && !items.length && <p className="staff-hint">Норм ещё нет. Соберите задания из архива, затем включите нужные и поставьте сумму.</p>}
      <div className="deed-lines">
        {items.map((item) => (
          <article key={item.actionType} className="staff-member-row deed-rate">
            <label className="deed-check">
              <input type="checkbox" checked={item.enabled} onChange={(event) => patch(item.actionType, 'enabled', event.target.checked)} />
              <span>{item.enabled ? 'Платим' : 'Выключено'}</span>
            </label>
            <label className="deed-field">
              <span>Название</span>
              <input className="panel-users-input" value={item.title} onChange={(event) => patch(item.actionType, 'title', event.target.value)} />
            </label>
            {item.enabled && !(Number(item.rewardKut) > 0) && (
              <p className="staff-answer-a">Включено, сумма 0: администратор увидит норму, деньги не начислятся.</p>
            )}
            <label className="deed-field">
              <span>Сколько дел</span>
              <input className="panel-users-input" inputMode="numeric" value={item.everyN} onChange={(event) => patch(item.actionType, 'everyN', Number(event.target.value.replace(/[^\d]/g, '')) || 0)} />
            </label>
            <label className="deed-field">
              <span>Кут</span>
              <input className="panel-users-input" inputMode="numeric" value={item.rewardKut} onChange={(event) => patch(item.actionType, 'rewardKut', Number(event.target.value.replace(/[^\d]/g, '')) || 0)} />
            </label>
            <label className="deed-field">
              <span>Откуда деньги</span>
              <select className="panel-users-input" value={item.purse} onChange={(event) => patch(item.actionType, 'purse', event.target.value)}>
                <option value="tech">Кут с технических групп</option>
                <option value="manual">Создатель платит сам</option>
              </select>
            </label>
          </article>
        ))}
      </div>
      <div className="deed-choice">
        <button type="button" className="sec-btn sec-btn-ghost" disabled={Boolean(busy)} onClick={collect}>
          {busy === 'collect' ? 'Смотрим архив…' : 'Собрать задания из архива'}
        </button>
        <button type="button" className="sec-btn" disabled={Boolean(busy) || !ready} onClick={save}>
          {busy === 'save' ? 'Сохраняем…' : 'Сохранить нормы'}
        </button>
      </div>
    </div>
  )
}

export default function DeedPay({ isProjectCreator = false }) {
  const [view, setView] = useState(isProjectCreator ? 'review' : 'mine')
  const [sort, setSort] = useState('new')
  const [action, setAction] = useState('')
  const [adminId, setAdminId] = useState(0)
  const [queue, setQueue] = useState(null)
  const [done, setDone] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [leaving, setLeaving] = useState('')
  const [flash, setFlash] = useState('')

  const load = useCallback(async () => {
    if (!isProjectCreator || isPanelPreviewMode()) return
    setError('')
    try {
      const [next, history] = await Promise.all([
        fetchDeedQueue({ sort, action, adminId }),
        fetchDeedDone({ sort, action, adminId }),
      ])
      setQueue(next)
      setDone(history.items || [])
    } catch (err) {
      setError(messageOf(err))
    }
  }, [isProjectCreator, sort, action, adminId])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    setFlash('')
  }, [sort, action, adminId])

  const decide = useCallback(async (kind) => {
    const id = queue?.card?.id
    if (!id || busy || leaving) return
    setError('')
    const side = kind === 'keep' ? 'right' : 'left'
    if (!motionQuiet()) {
      setLeaving(side)
      await wait(220)
    }
    setBusy(true)
    try {
      if (kind === 'keep') await keepDeed(id)
      else await dropDeed(id)
      setFlash(kind === 'keep'
        ? 'Принято. Дело вошло в зарплату администратора.'
        : 'Отклонено. В оплату не вошло. Наказание остаётся в архиве.')
      setLeaving('')
      await load()
    } catch (err) {
      setLeaving('')
      setError(messageOf(err))
    } finally {
      setBusy(false)
    }
  }, [queue, busy, leaving, load])

  useEffect(() => {
    if (view !== 'review' || !isProjectCreator) return undefined
    const onKey = (event) => {
      const tag = event.target?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      if (event.key === 'ArrowLeft') {
        event.preventDefault()
        decide('drop')
      } else if (event.key === 'ArrowRight') {
        event.preventDefault()
        decide('keep')
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [view, isProjectCreator, decide])

  const views = useMemo(() => {
    const list = []
    if (isProjectCreator) {
      list.push({ id: 'review', label: 'Проверка' })
      list.push({ id: 'rates', label: 'Нормы' })
    }
    list.push({ id: 'mine', label: 'Мои куты' })
    return list
  }, [isProjectCreator])

  const card = queue?.card

  return (
    <div className="deed-desk">
      <nav className="sec-tabs deed-views" aria-label="Оплата за дела">
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

      {view === 'mine' && <DeedMine isProjectCreator={isProjectCreator} />}
      {view === 'rates' && isProjectCreator && <DeedRates />}

      {view === 'review' && isProjectCreator && (
        <>
          {isPanelPreviewMode() ? (
            <p className="staff-hint">В копии панели проверка наказаний закрыта. Решения принимаются в настоящей панели.</p>
          ) : (
            <>
              <p className="deed-sum">Ждёт {queue?.waiting ?? '…'}</p>
              <p className="deed-lead">
                Одна карточка из архива. Слева дело не входит в оплату, справа входит. Стрелки на клавиатуре делают то же самое.
              </p>
              {flash && <p className="deed-flash" role="status">{flash}</p>}
              <div className="deed-filters" role="group" aria-label="Сортировка">
                {SORTS.map((item) => (
                  <button key={item.id} type="button" className={`sec-btn sec-btn-sm${sort === item.id ? '' : ' sec-btn-ghost'}`} onClick={() => setSort(item.id)}>
                    {item.label}
                  </button>
                ))}
              </div>
              <div className="deed-filters" role="group" aria-label="Тип наказания">
                {ACTIONS.map((item) => (
                  <button key={item.id || 'all'} type="button" className={`sec-btn sec-btn-sm${action === item.id ? '' : ' sec-btn-ghost'}`} onClick={() => setAction(item.id)}>
                    {item.label}
                  </button>
                ))}
              </div>
              {(queue?.admins || []).length > 0 && (
                <label className="deed-field">
                  <span>Администратор</span>
                  <select className="panel-users-input" value={adminId} onChange={(event) => setAdminId(Number(event.target.value) || 0)}>
                    <option value="0">Все администраторы</option>
                    {queue.admins.map((person) => (
                      <option key={person.id} value={person.id}>{person.name} · ждёт {person.waiting}</option>
                    ))}
                  </select>
                </label>
              )}
              {error && <p className="staff-hint">{error}</p>}
              <DeedPayouts />
              {!queue && !error && <p className="staff-hint">Открываем очередь…</p>}
              {queue && !card && !error && <p className="staff-hint">Новых наказаний с таким фильтром нет.</p>}
              {card && <DeedCard card={card} leaving={leaving} />}
              {card && (
                <div className="deed-choice">
                  <button type="button" className="sec-btn sec-btn-ghost deed-no" disabled={busy || Boolean(leaving)} onClick={() => decide('drop')}>
                    <span>Отклонить</span>
                    <small>не в зарплату</small>
                  </button>
                  <button type="button" className="sec-btn deed-yes" disabled={busy || Boolean(leaving)} onClick={() => decide('keep')}>
                    <span>Принять</span>
                    <small>в зарплату</small>
                  </button>
                </div>
              )}
              {done.length > 0 && (
                <div className="deed-lines">
                  <h3 className="staff-punish-title">Что уже решено</h3>
                  {done.map((item) => (
                    <article key={item.id} className="staff-member-row">
                      <div className="staff-member-info">
                        <span className="staff-card-name">
                          {item.status === 'kept' ? 'Засчитано' : 'Не в зарплате'} · {item.actionLabel}
                        </span>
                        <span className="staff-card-date">
                          {item.adminName} → {item.targetName} · {item.reason || 'без причины'} · {when(item.reviewedAt)}
                        </span>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}
