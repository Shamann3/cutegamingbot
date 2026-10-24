import { useCallback, useEffect, useMemo, useState } from 'react'
import PhotoLook from '../../../components/PhotoLook'
import { BAND_LABEL } from '../../../lib/deedSort'
import {
  clearPersonRates,
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
  savePersonRates,
} from '../../../lib/adminClient'
import RateTune from './RateTune'

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
  'Проверки администраторов': ['проверка', 'проверки', 'проверок'],
  'Проверки сотрудников': ['проверка', 'проверки', 'проверок'],
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

export function DeedPayouts() {
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
    return <p className="staff-hint">{error || 'Считаем засчитанные наказания…'}</p>
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
            ? `Ещё ${countPhrase(next.left, next.title)} — и ${money(next.rewardKut)}. Деньги приходят, когда создатель согласен с вашей проверкой.`
            : 'Когда создатель включит оплату и поставит сумму, здесь будет видно, сколько кут даёт каждое действие.'}
      </p>
      {Number(data?.checksOpen) > 0 && (
        <p className="deed-lead">Ваши проверки ждут решения создателя: {data.checksOpen}.</p>
      )}
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
                    : 'Сумма за этот тип пока не назначена, поэтому выплаты по нему нет.'}
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
          ? (
            <PhotoLook
              fileId={card.proofMediaId}
              eager
              alt="Фото-доказательство"
            />
          )
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
        {card.direct && <p className="work-band">Некому было разобрать. Решение сразу ваше.</p>}
        {card.sortLabel && (
          <p className="work-band">
            Разобрал администратор: {card.sortLabel}{card.sorterName ? ` · ${card.sorterName}` : ''}
          </p>
        )}
        {!card.direct && !card.sortLabel && card.band && (
          <p className="work-band">{BAND_LABEL[card.band]}</p>
        )}
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

export function DeedRates() {
  const [items, setItems] = useState([])
  const [people, setPeople] = useState({ admins: [], staff: [] })
  const [own, setOwn] = useState([])
  const [who, setWho] = useState(0)
  const [personDraft, setPersonDraft] = useState(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState('')
  const [tuneStamp, setTuneStamp] = useState(0)

  const applyPayload = (data) => {
    setItems(data.items || [])
    setPeople(data.people || { admins: [], staff: [] })
    setOwn(data.own || [])
    setReady(true)
  }

  const load = useCallback(async () => {
    setError('')
    try {
      applyPayload(await fetchDeedRates())
    } catch (err) {
      setError(messageOf(err))
    }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!who) {
      setPersonDraft(null)
      return
    }
    setPersonDraft(items.map((item) => {
      const custom = own.find((row) => row.userId === who && row.actionType === item.actionType)
      if (!custom) return { ...item, ordinary: true }
      return {
        ...item,
        everyN: custom.everyN,
        rewardKut: custom.rewardKut,
        enabled: custom.enabled,
        ordinary: false,
      }
    }))
  }, [who, items, own])

  const patch = (actionType, field, value) => {
    setItems((prev) => prev.map((item) => (item.actionType === actionType ? { ...item, [field]: value } : item)))
  }

  const patchPerson = (actionType, field, value) => {
    setPersonDraft((prev) => (prev || []).map((item) => (
      item.actionType === actionType ? { ...item, [field]: value } : item
    )))
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
      applyPayload(await saveDeedRates(clean))
      setNotice('Обычные нормы сохранены. Личные остались у тех, кому вы их ставили. Автоподстройка выключена.')
      setTuneStamp((value) => value + 1)
    } catch (err) {
      setError(messageOf(err))
    } finally {
      setBusy('')
    }
  }

  const savePerson = async () => {
    if (!who || !personDraft) return
    setBusy('person')
    setError('')
    setNotice('')
    try {
      const data = await savePersonRates({
        userId: who,
        items: personDraft.map((item) => ({
          actionType: item.actionType,
          everyN: Math.max(1, Number(item.everyN) || 1),
          rewardKut: Math.max(0, Number(item.rewardKut) || 0),
          enabled: Boolean(item.enabled),
          ordinary: Boolean(item.ordinary),
        })),
      })
      applyPayload(data)
      setNotice('Нормы этого человека сохранены. Остальные по-прежнему на обычных.')
    } catch (err) {
      setError(messageOf(err))
    } finally {
      setBusy('')
    }
  }

  const ordinaryAll = async () => {
    setBusy('ordinary')
    setError('')
    setNotice('')
    try {
      applyPayload(await clearPersonRates())
      setWho(0)
      setNotice('Личные нормы сняты. У всех снова обычные числа.')
      setTuneStamp((value) => value + 1)
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

  const rows = who ? (personDraft || []) : items
  const ownPeople = new Set(own.map((row) => row.userId)).size
  const samePerson = Boolean(who)
    && people.admins.some((person) => person.id === who)
    && people.staff.some((person) => person.id === who)

  return (
    <div className="deed-rates">
      <RateTune stamp={tuneStamp} onDone={() => load()} />
      <label className="deed-field norm-who">
        <span>Кому эта норма</span>
        <select
          className="panel-users-input"
          value={who}
          onChange={(event) => setWho(Number(event.target.value) || 0)}
        >
          <option value="0">Всем сразу</option>
          {people.admins.length > 0 && (
            <optgroup label="Администраторы групп">
              {people.admins.map((person) => (
                <option key={`admin-${person.id}`} value={person.id}>{person.name}</option>
              ))}
            </optgroup>
          )}
          {people.staff.length > 0 && (
            <optgroup label="Сотрудники проекта">
              {people.staff.map((person) => (
                <option key={`staff-${person.id}`} value={person.id}>{person.name}</option>
              ))}
            </optgroup>
          )}
        </select>
      </label>
      <p className="norm-scope">
        {who
          ? 'Числа ниже только у этого человека. У остальных останется обычная норма.'
          : 'Эти числа получат все, у кого нет своей нормы.'}
        {ownPeople > 0 ? ` Своя норма сейчас у ${ownPeople}.` : ''}
        {samePerson ? ' Он и администратор, и сотрудник — норма одна.' : ''}
      </p>
      {error && <p className="staff-hint" role="alert">{error}</p>}
      {notice && <p className="staff-hint" role="status">{notice}</p>}
      {!ready && !error && <p className="staff-hint">Открываем нормы…</p>}
      {ready && !items.length && <p className="staff-hint">Норм ещё нет. Соберите задания из архива, затем включите нужные и поставьте сумму.</p>}
      <div className="deed-lines">
        {rows.map((item) => {
          const base = items.find((row) => row.actionType === item.actionType) || item
          const custom = Boolean(who) && !item.ordinary
          const showFormula = !who ? item.enabled : custom && item.enabled
          const title = (who ? base.title : item.title) || item.actionType
          const setCount = (raw) => {
            const value = Number(String(raw).replace(/[^\d]/g, '')) || 0
            if (who) patchPerson(item.actionType, 'everyN', value)
            else patch(item.actionType, 'everyN', value)
          }
          const setPay = (raw) => {
            const value = Number(String(raw).replace(/[^\d]/g, '')) || 0
            if (who) patchPerson(item.actionType, 'rewardKut', value)
            else patch(item.actionType, 'rewardKut', value)
          }
          const purse = who ? base.purse : item.purse
          const purseWords = purse === 'manual' ? 'создатель платит сам' : 'из технических групп'
          return (
            <article key={item.actionType} className={`norm-card${showFormula ? '' : ' is-off'}`}>
              <header className="norm-head">
                <strong>{title}</strong>
                {who && item.ordinary && <span className="norm-pill">как у всех</span>}
                {who && !item.ordinary && <span className="norm-pill is-own">своя</span>}
                {!who && (
                  <label className="norm-pay">
                    <input type="checkbox" checked={item.enabled} onChange={(event) => patch(item.actionType, 'enabled', event.target.checked)} />
                    <span>{item.enabled ? 'Платим' : 'Не платим'}</span>
                  </label>
                )}
                {custom && (
                  <label className="norm-pay">
                    <input type="checkbox" checked={item.enabled} onChange={(event) => patchPerson(item.actionType, 'enabled', event.target.checked)} />
                    <span>{item.enabled ? 'Платим ему' : 'Ему не платим'}</span>
                  </label>
                )}
              </header>

              {who && item.ordinary && (
                <p className="norm-read">
                  {base.enabled
                    ? `Как у всех: каждые ${base.everyN} · ${base.title || title} = ${base.rewardKut} кут, ${base.purse === 'manual' ? 'создатель платит сам' : 'из технических групп'}.`
                    : 'У всех этот вид выключен. Своя норма может включить оплату только ему.'}
                </p>
              )}
              {who && item.ordinary && (
                <button type="button" className="sec-btn sec-btn-ghost sec-btn-sm" onClick={() => patchPerson(item.actionType, 'ordinary', false)}>
                  Поставить свою норму
                </button>
              )}

              {!showFormula && !item.ordinary && (
                <p className="norm-read">За этот вид сейчас не платим.</p>
              )}

              {showFormula && (
                <>
                  <div className="norm-formula">
                    <span>Каждые</span>
                    <input
                      className="panel-users-input"
                      inputMode="numeric"
                      aria-label={`Сколько дел: ${title}`}
                      value={item.everyN}
                      onChange={(event) => setCount(event.target.value)}
                    />
                    <span>дел</span>
                    <span className="norm-eq" aria-hidden="true">=</span>
                    <input
                      className="panel-users-input"
                      inputMode="numeric"
                      aria-label={`Кут: ${title}`}
                      value={item.rewardKut}
                      onChange={(event) => setPay(event.target.value)}
                    />
                    <span>кут</span>
                  </div>
                  <p className="norm-read">
                    {Number(item.rewardKut) > 0
                      ? `Каждые ${item.everyN || 0} · ${title} = ${item.rewardKut} кут, ${purseWords}.`
                      : `Каждые ${item.everyN || 0} · ${title}: сумма 0, деньги не начислятся.`}
                  </p>
                  {!who && (
                    <label className="norm-purse">
                      <span>Откуда деньги</span>
                      <select className="panel-users-input" value={item.purse} onChange={(event) => patch(item.actionType, 'purse', event.target.value)}>
                        <option value="tech">Из технических групп</option>
                        <option value="manual">Создатель платит сам</option>
                      </select>
                    </label>
                  )}
                  {!who && (
                    <label className="norm-purse">
                      <span>Название в списках</span>
                      <input className="panel-users-input" value={item.title} aria-label={`Название: ${item.actionType}`} onChange={(event) => patch(item.actionType, 'title', event.target.value)} />
                    </label>
                  )}
                </>
              )}

              {custom && (
                <button type="button" className="sec-btn sec-btn-ghost sec-btn-sm" onClick={() => patchPerson(item.actionType, 'ordinary', true)}>
                  Вернуть как у всех
                </button>
              )}
            </article>
          )
        })}
      </div>
      <div className="deed-choice">
        {!who && (
          <button type="button" className="sec-btn sec-btn-ghost" disabled={Boolean(busy)} onClick={collect}>
            {busy === 'collect' ? 'Смотрим архив…' : 'Собрать задания из архива'}
          </button>
        )}
        <button
          type="button"
          className="sec-btn sec-btn-ghost"
          disabled={Boolean(busy) || ownPeople === 0}
          onClick={ordinaryAll}
        >
          {busy === 'ordinary' ? 'Снимаем…' : 'Обычные нормы всем'}
        </button>
        <button
          type="button"
          className="sec-btn"
          disabled={Boolean(busy) || !ready || (Boolean(who) && !personDraft)}
          onClick={who ? savePerson : save}
        >
          {busy === 'save' || busy === 'person' ? 'Сохраняем…' : who ? 'Сохранить этому человеку' : 'Сохранить обычные нормы'}
        </button>
      </div>
    </div>
  )
}

export default function DeedPay({ isProjectCreator = false }) {
  const [view, setView] = useState(isProjectCreator ? 'review' : 'mine')
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
      const nextPromise = fetchDeedQueue({ action, adminId })
      const historyPromise = fetchDeedDone({ action, adminId })
      try {
        const next = await nextPromise
        setQueue(next)
        setError('')
      } catch (err) {
        setError(messageOf(err))
      }
      try {
        const history = await historyPromise
        setDone(history.items || [])
      } catch {
        setDone([])
      }
    } catch (err) {
      setError(messageOf(err))
    }
  }, [isProjectCreator, action, adminId])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    setFlash('')
  }, [action, adminId])

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
      if (document.querySelector('.photo-look')) return
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
                Сначала принятые, потом неверные, потом те, что невозможно решить.
                Если разобрать было некому, карточка приходит сразу.
                В зарплату входит только то, что вы смахнули вправо.
                Фото открывается целиком. Стрелки на клавиатуре: влево отклонить, вправо принять.
              </p>
              {flash && <p className="deed-flash" role="status">{flash}</p>}
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
              <DeedPayouts />
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
