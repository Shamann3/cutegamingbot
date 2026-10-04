import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { searchAdminUsers } from '../lib/adminClient'
import { CABINET_PAGE_DEFS, cabinetPagesFor, groupCabinetTabs } from '../lib/panelPreview'
import { PAGE_RIGHTS, PUNISH_RIGHTS, TELEGRAM_ADMIN_RIGHTS } from '../lib/realmRights'
import FocusWindow from './FocusWindow'
import RightSwitch from './RightSwitch'

function RightList({ items, rights, locked, onToggle, compareSet }) {
  return (
    <div className="realm-right-grid">
      {items.map((item) => {
        const on = rights.has(item.id)
        const lowerOn = compareSet ? compareSet.has(item.id) : null
        const hint = [
          item.hint,
          lowerOn === true && !on ? 'У младшей должности включено' : null,
          lowerOn === false && on ? 'У младшей должности выключено' : null,
        ].filter(Boolean).join(' · ')
        return (
          <RightSwitch
            key={item.id}
            on={on}
            disabled={locked}
            title={item.label}
            hint={hint}
            onChange={(next) => onToggle(item.id, next)}
          />
        )
      })}
    </div>
  )
}

function lowerRankPeer(positions, rank) {
  const juniors = (positions || [])
    .filter((row) => Number(row.rank) < Number(rank))
    .sort((a, b) => Number(b.rank) - Number(a.rank))
  return juniors[0] || null
}

function rankCaption(row) {
  if (row.kind === 'spamblock') return 'Спам-блок · ранг 0 · без наказаний'
  if (row.kind === 'member' || Number(row.rank) <= 0) return 'Ранг 0 · как обычный участник'
  return `Ранг ${row.rank}`
}

function tabCaption(row) {
  if (Number(row.rank) >= 5) return 'все вкладки'
  const count = cabinetPagesFor(row).length
  if (!count) return 'только главная'
  return `${count} ${count === 1 ? 'вкладка' : count < 5 ? 'вкладки' : 'вкладок'}`
}

function toneOf(title, rank) {
  if (Number(rank) >= 5) return 'creator'
  const text = String(title || '').toLowerCase()
  if (text.includes('админ')) return 'admin'
  if (text.includes('модер')) return 'mod'
  if (text.includes('хелп') || text.includes('help')) return 'help'
  return 'seat'
}

export default function PositionEditor({
  positions,
  creator,
  onSave,
  savingId,
  onPreview = null,
  chatId = 0,
  seats = [],
  onDelete = null,
  onAppoint = null,
}) {
  const [drafts, setDrafts] = useState(positions || [])
  const [openId, setOpenId] = useState(null)

  useEffect(() => {
    setDrafts(positions || [])
  }, [positions])

  const byId = useMemo(() => {
    const map = new Map()
    for (const row of drafts) map.set(row.id, row)
    return map
  }, [drafts])

  const ordered = useMemo(
    () => [...drafts].sort((a, b) => Number(b.rank) - Number(a.rank)),
    [drafts],
  )

  const patch = (id, next) => {
    setDrafts((rows) => rows.map((row) => (row.id === id ? { ...row, ...next } : row)))
  }

  if (!drafts.length) {
    return <p className="realm-copy">Должностей пока нет. Создайте свою или отметьте группу официальной.</p>
  }

  const open = byId.get(openId) || null

  return (
    <div className="role-ladder">
      {ordered.map((row) => {
        const rights = new Set(row.rights || [])
        return (
          <button
            key={row.id}
            type="button"
            className={`role-card is-${toneOf(row.title, row.rank)}`}
            onClick={() => setOpenId(row.id)}
          >
            <span className="role-card-rank">{rankCaption(row)}</span>
            <strong>{row.title}</strong>
            <span>{tabCaption(row)} · {rights.size} прав · нажать, чтобы настроить</span>
          </button>
        )
      })}
      {open && (
        <PositionSheet
          row={open}
          drafts={drafts}
          byId={byId}
          creator={creator}
          savingId={savingId}
          onPreview={creator ? onPreview : null}
          chatId={chatId}
          seats={(seats || []).filter((person) => Number(person.positionId) === Number(open.id))}
          onDelete={onDelete}
          onAppoint={onAppoint}
          onClose={() => setOpenId(null)}
          onPatch={patch}
          onSave={onSave}
        />
      )}
    </div>
  )
}

function personBits(person) {
  if (!person) return null
  const id = Number(person.userId ?? person.user_id)
  if (!Number.isFinite(id) || id <= 0) return null
  const username = person.username ? `@${String(person.username).replace(/^@/, '')}` : ''
  const name = person.displayName || person.firstName || person.first_name || person.name || (username || String(id))
  return { id, name, username }
}

function typedId(value) {
  const bare = String(value || '').trim().replace(/^@/, '')
  if (!/^\d{1,15}$/.test(bare)) return null
  const id = Number(bare)
  return id > 0 ? id : null
}

function RolePersonField({ text, onText, userId, onUserId }) {
  const [hits, setHits] = useState([])
  const [phase, setPhase] = useState('idle')
  const [picked, setPicked] = useState(null)
  const onUserIdRef = useRef(onUserId)
  onUserIdRef.current = onUserId
  const inputRef = useRef(null)

  useEffect(() => {
    const query = String(text || '').trim()
    const bare = query.replace(/^@/, '')
    if (bare.length < 2) {
      setHits([])
      setPicked(null)
      setPhase('idle')
      return undefined
    }
    let cancelled = false
    const timer = window.setTimeout(async () => {
      setPhase('loading')
      try {
        const data = await searchAdminUsers(query)
        if (cancelled) return
        const items = (Array.isArray(data?.results) ? data.results : Array.isArray(data?.items) ? data.items : []).slice(0, 6)
        setHits(items)
        const exact = items
          .map((item) => ({ item, bits: personBits(item) }))
          .find(({ bits }) => bits && (String(bits.id) === bare || bits.username.replace(/^@/, '').toLowerCase() === bare.toLowerCase()))
        if (exact?.bits) {
          setPicked(exact.item)
          onUserIdRef.current(exact.bits.id)
          setPhase('ready')
        } else {
          setPicked(null)
          setPhase(items.length ? 'ready' : 'empty')
        }
      } catch {
        if (cancelled) return
        setHits([])
        setPicked(null)
        setPhase('error')
      }
    }, 180)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [text])

  const type = (value) => {
    onText(value)
    onUserId(typedId(value))
    setPicked(null)
  }

  const choose = (person) => {
    const bits = personBits(person)
    if (!bits) return
    setPicked(person)
    onUserId(bits.id)
    onText(bits.username || bits.name)
    inputRef.current?.focus()
  }

  const chosen = personBits(picked)
  const shownId = chosen?.id || userId

  return (
    <div className="role-person">
      <label htmlFor="role-person-input">Кому</label>
      <div className="role-person-box">
        <input
          id="role-person-input"
          ref={inputRef}
          type="text"
          inputMode="text"
          autoComplete="off"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          enterKeyHint="search"
          placeholder="@username, имя или id"
          value={text}
          onChange={(event) => type(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== 'Enter') return
            event.preventDefault()
            if (hits.length === 1) choose(hits[0])
          }}
        />
        {text ? (
          <button type="button" className="role-person-clear" onClick={() => type('')}>
            Стереть
          </button>
        ) : null}
      </div>
      {phase === 'loading' && <p className="role-person-status">Ищем…</p>}
      {phase === 'empty' && !typedId(text) && <p className="role-person-status">Такого человека нет. Проверьте @username или впишите id.</p>}
      {phase === 'error' && <p className="role-person-status">Поиск не ответил. Id можно вписать цифрами — должность уйдёт на него.</p>}
      {chosen && (
        <p className="role-person-chosen" role="status">
          Выбран {chosen.name}{chosen.username ? ` · ${chosen.username}` : ''} · {chosen.id}
        </p>
      )}
      {!chosen && shownId && <p className="role-person-chosen" role="status">Назначение по id {shownId}</p>}
      {hits.length > 0 && (
        <ul className="role-person-list" role="listbox" aria-label="Люди">
          {hits.map((person) => {
            const bits = personBits(person)
            if (!bits) return null
            const on = bits.id === shownId
            return (
              <li key={bits.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={on}
                  className={on ? 'is-on' : ''}
                  onClick={() => choose(person)}
                >
                  <span className="role-person-mark" aria-hidden="true">{(bits.name || '?').slice(0, 1).toUpperCase()}</span>
                  <span>
                    <strong>{bits.name}</strong>
                    <em>{bits.username || 'без username'} · {bits.id}</em>
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

function defaultPrefix(row) {
  if (!row || row.kind === 'member') return ''
  if (row.kind === 'spamblock') return row.prefix || 'спам блок'
  return row.prefix || String(row.title || '').trim().slice(0, 16)
}

function PositionSheet({
  row,
  drafts,
  byId,
  creator,
  savingId,
  chatId,
  seats,
  onDelete,
  onAppoint,
  onClose,
  onPatch,
  onSave,
  onPreview,
}) {
  const frozen = row.kind === 'spamblock' || row.kind === 'member' || Number(row.rank) <= 0
  const locked = row.rank >= 5 || frozen
  const reduce = useReducedMotion()
  const rights = new Set(row.rights || [])
  const pageIds = cabinetPagesFor(row.rank >= 5 ? { ...row, pages: CABINET_PAGE_DEFS.map((item) => item.id) } : row)
  const dock = groupCabinetTabs(
    row.rights,
    false,
    locked ? undefined : pageIds,
    row.rank,
  )
  const pages = PAGE_RIGHTS.filter((item) => creator || item.id !== 'manage_positions')
  const peer = lowerRankPeer(drafts, row.rank)
  const compareSet = peer ? new Set(byId.get(peer.id)?.rights || peer.rights || []) : null
  const toggle = (rightId, on) => {
    const next = new Set(rights)
    if (on) next.add(rightId)
    else next.delete(rightId)
    onPatch(row.id, { rights: [...next] })
  }
  const togglePage = (pageId, on) => {
    const next = new Set(pageIds)
    if (on) next.add(pageId)
    else next.delete(pageId)
    onPatch(row.id, {
      pages: CABINET_PAGE_DEFS.map((item) => item.id).filter((id) => next.has(id)),
    })
  }
  const [personText, setPersonText] = useState('')
  const [userId, setUserId] = useState(null)
  const [prefix, setPrefix] = useState(() => defaultPrefix(row))
  const [reason, setReason] = useState('')
  const [termStart, setTermStart] = useState('')
  const [termEnd, setTermEnd] = useState('')
  const [busy, setBusy] = useState('')
  const [footError, setFootError] = useState('')
  const [footNote, setFootNote] = useState('')
  const [entryKey, setEntryKey] = useState('')
  const canManage = Boolean(creator) && Number(row.rank) < 5
  const spam = row.kind === 'spamblock'

  useEffect(() => {
    setPersonText('')
    setUserId(null)
    setPrefix(defaultPrefix(row))
    setReason('')
    setTermStart('')
    setTermEnd('')
    setFootError('')
    setFootNote('')
    setEntryKey('')
  }, [row.id])

  const appoint = async () => {
    if (!onAppoint) return
    if (!userId) {
      setFootError('Впишите @username, имя или id и выберите человека')
      return
    }
    if (spam && !termEnd) {
      setFootError('Укажите, по какое число держать спам-блок')
      return
    }
    setBusy('appoint')
    setFootError('')
    setFootNote('')
    setEntryKey('')
    try {
      const data = await onAppoint(row, {
        userId,
        prefix,
        reason,
        termStart,
        termEnd,
      })
      setEntryKey(data?.entryKey || '')
      setFootNote(data?.telegram || `Должность «${row.title}» назначена`)
      setPersonText('')
      setUserId(null)
      setReason('')
    } catch (err) {
      setFootError(err?.message || 'Назначить не удалось')
    } finally {
      setBusy('')
    }
  }

  const remove = async () => {
    if (!onDelete) return
    const held = (seats || []).length
    const who = held
      ? ` Сейчас её держат ${held}. У них должность и префикс в чате снимутся, из группы их не исключит.`
      : ' Людей с этой должностью сейчас нет.'
    if (!window.confirm(`Удалить должность «${row.title}»?${who}`)) return
    setBusy('delete')
    setFootError('')
    try {
      await onDelete(row)
      onClose()
    } catch (err) {
      setFootError(err?.message || 'Удалить должность не удалось')
      setBusy('')
    }
  }

  const foot = (footError || footNote || (canManage && onDelete)) ? (
    <div className="role-delete-bar">
      {footError && <p className="realm-alert" role="alert">{footError}</p>}
      {footNote && <p className="realm-note" role="status">{footNote}</p>}
      {entryKey && <p className="realm-alert" data-copyable="1">Личный ключ, один показ: {entryKey}</p>}
      {canManage && onDelete && (
        <>
          <p className="realm-copy">Люди остаются в группе. Должность и префикс в чате снимаются.</p>
          <button type="button" className="role-delete" disabled={busy === 'delete'} onClick={remove}>
            {busy === 'delete' ? 'Удаляю…' : 'Удалить должность'}
          </button>
        </>
      )}
    </div>
  ) : null

  return (
    <FocusWindow
      title={row.title || 'Должность'}
      subtitle={
        row.rank >= 5
          ? 'Создатель группы. Права полные, снять их нельзя.'
          : row.kind === 'spamblock'
            ? 'Спам-блок. Наказаний нет и включить их нельзя. Срок задаётся при назначении.'
            : frozen
              ? 'Ранг 0. Только то, что и так может обычный участник: писать. Наказаний нет.'
              : `Ранг ${row.rank}. Сначала вкладки нижней полосы, потом что можно делать внутри. Наказать можно только того, кто младше.`
      }
      onClose={onClose}
      footer={foot}
    >
      <fieldset className="realm-rights-block cabinet-tabs" disabled={locked}>
        <legend>Вкладки кабинета</legend>
        <p className="realm-copy">
          Главная и «Ещё» остаются. Остальное включается здесь и записывается при сохранении.
          Выключенная вкладка пропадает из нижней полосы.
        </p>
        <ul className="cabinet-dock-preview" aria-live="polite" aria-label="Нижняя полоса этой должности">
          <AnimatePresence initial={false}>
            {dock.map((item) => (
              <motion.li
                key={item.id}
                layout={!reduce}
                initial={reduce ? false : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduce ? undefined : { opacity: 0, y: -6 }}
                transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
              >
                {item.label}
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
        <div className="cabinet-tab-list">
          {CABINET_PAGE_DEFS.map((item) => (
            <RightSwitch
              key={item.id}
              on={pageIds.includes(item.id)}
              disabled={locked}
              title={item.label}
              hint={item.hint}
              onChange={(next) => togglePage(item.id, next)}
            />
          ))}
        </div>
      </fieldset>
      {canManage && onAppoint && (
        <div className="role-sheet-foot">
          <h3 className="realm-h">Назначить эту должность</h3>
          <p className="realm-copy">
            Впишите @username, имя или id. Человек сразу получает должность в этой группе
            {row.kind === 'member' ? ', без префикса в чате.' : ', с префиксом в чате.'}
          </p>
          <RolePersonField
            text={personText}
            onText={setPersonText}
            userId={userId}
            onUserId={setUserId}
          />
          {row.kind !== 'member' && (
            <label>Префикс в чате
              <input value={prefix} maxLength={16} onChange={(event) => setPrefix(event.target.value)} />
            </label>
          )}
          {spam && (
            <div className="role-sheet-dates">
              <label>С какого числа
                <input type="date" value={termStart} onChange={(event) => setTermStart(event.target.value)} />
              </label>
              <label>По какое число
                <input type="date" value={termEnd} onChange={(event) => setTermEnd(event.target.value)} />
              </label>
            </div>
          )}
          <label>Для чего
            <input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Можно оставить пустым" />
          </label>
          {(seats || []).length > 0 && (
            <>
              <p className="realm-copy">Сейчас её держат</p>
              <ul className="role-holders">
                {seats.map((person) => (
                  <li key={person.userId}>
                    <strong>{person.name || person.userId}</strong>
                    <span>{person.username ? `@${String(person.username).replace(/^@/, '')}` : person.userId}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
          <button type="button" className="realm-back" disabled={busy === 'appoint' || !chatId} onClick={appoint}>
            {busy === 'appoint' ? 'Назначаю…' : 'Назначить эту должность'}
          </button>
        </div>
      )}
      <form
        className="realm-form role-sheet-form"
        onSubmit={(event) => {
          event.preventDefault()
          onSave(row)
        }}
      >
        <label>
          Название
          <input
            value={row.title}
            onChange={(event) => onPatch(row.id, { title: event.target.value })}
          />
        </label>
        {peer && (
          <p className="realm-note" role="status">
            Ориентир — младшая должность «{peer.title}» (ранг {peer.rank}).
          </p>
        )}
        <fieldset className="realm-rights-block" disabled={locked}>
          <legend>Что можно делать</legend>
          <RightList items={pages} rights={rights} locked={locked} onToggle={toggle} compareSet={compareSet} />
        </fieldset>
        <fieldset className="realm-rights-block" disabled={locked}>
          <legend>Наказания в этом чате</legend>
          <RightList items={PUNISH_RIGHTS} rights={rights} locked={locked} onToggle={toggle} compareSet={compareSet} />
        </fieldset>
        <fieldset className="realm-rights-block" disabled={locked}>
          <legend>Права Telegram в чате</legend>
          <RightList
            items={TELEGRAM_ADMIN_RIGHTS}
            rights={rights}
            locked={locked}
            onToggle={toggle}
            compareSet={compareSet}
          />
        </fieldset>
        {onPreview && (
          <button
            type="button"
            className="realm-back"
            onClick={() => onPreview(row)}
          >
            Открыть копию кабинета
          </button>
        )}
        <button type="submit" className="realm-back" disabled={savingId === row.id || row.title.trim().length < 2}>
          {savingId === row.id ? 'Запись…' : 'Сохранить должность'}
        </button>
      </form>
    </FocusWindow>
  )
}
