import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, Reorder, motion, useDragControls, useReducedMotion } from 'framer-motion'
import { searchAdminUsers } from '../lib/adminClient'
import { CABINET_PAGE_DEFS, cabinetPagesFor, groupCabinetTabs } from '../lib/panelPreview'
import { isFloorPost, isOwnerPost, isStaffPost, ladderRanks, positionOrder, ranksDiffer } from '../lib/rankLadder'
import { PAGE_RIGHTS, PROJECT_RIGHTS, PUNISH_RIGHTS, TELEGRAM_ADMIN_RIGHTS } from '../lib/realmRights'
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

function rankCaption(row, rank = row?.rank) {
  if (isOwnerPost(row)) return 'Создатель группы · выше всех'
  if (row.kind === 'spamblock') return 'Спам-блок · ранг 0'
  if (row.kind === 'member' || Number(rank) <= 0) return 'Ранг 0'
  return `Ранг ${rank}`
}

function RoleCard({ row, onOpen, rank }) {
  const rights = new Set(row.rights || [])
  const shown = rank ?? row.rank
  const numeral = isStaffPost(row) && Number(shown) > 0
  return (
    <button
      type="button"
      className={`role-card is-${toneOf(row.title, shown)}`}
      onClick={onOpen}
    >
      <span className="role-card-rank">{rankCaption(row, shown)}</span>
      <span className="role-card-main">
        <strong>{row.title}</strong>
        {numeral && <span className="role-rank-num" aria-hidden="true">{shown}</span>}
      </span>
      <span>{tabCaption(row)} · {rights.size} прав · нажать, чтобы настроить</span>
    </button>
  )
}

function StaffRow({ row, rank, onOpen, onDrop, onMove, first, last, locked }) {
  const controls = useDragControls()
  const reduce = useReducedMotion()
  return (
    <Reorder.Item
      as="div"
      value={Number(row.id)}
      dragListener={false}
      dragControls={controls}
      onDragEnd={onDrop}
      className="role-row"
      whileDrag={reduce || locked ? undefined : { scale: 1.02, zIndex: 3 }}
    >
      <div className="role-shift">
        <button
          type="button"
          className="role-nudge"
          aria-label={`Выше, ${row.title}`}
          disabled={locked || first}
          onClick={() => onMove(row.id, -1)}
        >
          <span className="role-chevron" aria-hidden="true" />
        </button>
        <button
          type="button"
          className="role-grip"
          aria-label={`Перетащить, ${row.title}`}
          disabled={locked}
          onPointerDown={(event) => {
            if (locked) return
            controls.start(event)
          }}
        >
          <span aria-hidden="true" />
        </button>
        <button
          type="button"
          className="role-nudge"
          aria-label={`Ниже, ${row.title}`}
          disabled={locked || last}
          onClick={() => onMove(row.id, 1)}
        >
          <span className="role-chevron is-down" aria-hidden="true" />
        </button>
      </div>
      <RoleCard row={row} rank={rank} onOpen={onOpen} />
    </Reorder.Item>
  )
}

function tabCaption(row) {
  const count = cabinetPagesFor(row).length
  if (!count) return 'только главная'
  if (count >= CABINET_PAGE_DEFS.length) return 'все вкладки'
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
  onOrder = null,
  ordering = false,
  canReorder = false,
}) {
  const [drafts, setDrafts] = useState(positions || [])
  const [openId, setOpenId] = useState(null)

  useEffect(() => {
    setDrafts((current) => {
      const incoming = positions || []
      if (!current.length) return incoming
      const local = new Map(current.map((row) => [row.id, row]))
      return incoming.map((row) => {
        const prev = local.get(row.id)
        if (!prev) return row
        return {
          ...row,
          title: prev.title,
          rights: prev.rights,
          pages: prev.pages,
          prefix: prev.prefix,
        }
      })
    })
  }, [positions])

  const byId = useMemo(() => {
    const map = new Map()
    for (const row of drafts) map.set(row.id, row)
    return map
  }, [drafts])

  const ordered = useMemo(() => positionOrder(drafts), [drafts])
  const owners = ordered.filter(isOwnerPost)
  const floor = ordered.filter(isFloorPost)
  const staffRows = ordered.filter(isStaffPost)
  const staffKey = staffRows.map((row) => `${row.id}:${row.rank}:${row.ladder || 0}`).join('|')
  const [staffOrder, setStaffOrder] = useState(() => staffRows.map((row) => Number(row.id)))
  const orderRef = useRef(staffOrder)
  const sending = useRef(false)
  const pending = useRef(null)
  orderRef.current = staffOrder

  useEffect(() => {
    const next = positionOrder(staffRows).map((row) => Number(row.id))
    orderRef.current = next
    setStaffOrder(next)
  }, [staffKey])

  const patch = (id, next) => {
    setDrafts((rows) => rows.map((row) => (row.id === id ? { ...row, ...next } : row)))
  }

  const preview = useMemo(() => {
    const map = new Map()
    for (const item of ladderRanks(staffOrder)) map.set(item.id, item.rank)
    return map
  }, [staffOrder])

  const commitOrder = (ids, force = false) => {
    if (!onOrder) return
    const next = (ids || []).map(Number)
    const moved = next.join(',') !== staffRows.map((row) => Number(row.id)).join(',')
    if (!force && !moved) return
    const run = (batch) => {
      sending.current = true
      Promise.resolve(onOrder(batch)).finally(() => {
        const queued = pending.current
        pending.current = null
        if (queued && queued.join(',') !== batch.join(',')) {
          run(queued)
          return
        }
        sending.current = false
      })
    }
    if (sending.current) {
      pending.current = next
      return
    }
    run(next)
  }

  const moveStaff = (id, dir) => {
    const ids = orderRef.current.map(Number)
    const index = ids.indexOf(Number(id))
    const target = index + dir
    if (index < 0 || target < 0 || target >= ids.length) return
    const next = ids.slice()
    const [item] = next.splice(index, 1)
    next.splice(target, 0, item)
    orderRef.current = next
    setStaffOrder(next)
    commitOrder(next)
  }

  if (!drafts.length) {
    return <p className="realm-copy">Должностей пока нет. Создайте свою или отметьте группу официальной.</p>
  }

  const open = byId.get(openId) || null
  const reorderOn = Boolean(canReorder && onOrder && staffOrder.length > 0)
  const misaligned = reorderOn && !ordering && ranksDiffer(staffRows, staffOrder)
  const sameRank = staffRows.length > 1 && staffRows.every((row) => Number(row.rank) === Number(staffRows[0].rank))

  return (
    <div className="role-ladder">
      {owners.map((row) => (
        <RoleCard key={row.id} row={row} onOpen={() => setOpenId(row.id)} />
      ))}
      {reorderOn && (
        <p className="realm-copy role-ladder-note">
          Сверху старше. Потяните полоску или стрелку: первая должность получает ранг 4, затем 3, 2 и 1.
          Создатель группы выше всех и не двигается.
          {staffOrder.length > 4 ? ' Ниже четвёртого места ранг остаётся 1.' : ''}
        </p>
      )}
      {onOrder && !canReorder && !ordering && (
        <p className="realm-copy role-ladder-note">Очистите поиск, чтобы менять ранги.</p>
      )}
      {sameRank && reorderOn && (
        <p className="realm-note" role="status">
          Эти должности на одном ранге и не могут наказать друг друга. Цифра справа — ранг после записи. Нажмите «Записать ранги» или поднимите старшую вверх.
        </p>
      )}
      {ordering && <p className="realm-copy">Записываем ранги…</p>}
      {reorderOn ? (
        <Reorder.Group
          as="div"
          axis="y"
          values={staffOrder}
          onReorder={(next) => {
            const ids = next.map(Number)
            orderRef.current = ids
            setStaffOrder(ids)
          }}
          className="role-ladder-staff"
        >
          {staffOrder.map((id, index) => {
            const row = byId.get(id) || byId.get(String(id))
            if (!row) return null
            return (
              <StaffRow
                key={id}
                row={row}
                rank={preview.get(id) ?? row.rank}
                first={index === 0}
                last={index === staffOrder.length - 1}
                locked={ordering}
                onOpen={() => setOpenId(id)}
                onMove={moveStaff}
                onDrop={() => commitOrder(orderRef.current)}
              />
            )
          })}
        </Reorder.Group>
      ) : (
        staffRows.map((row) => (
          <RoleCard key={row.id} row={row} onOpen={() => setOpenId(row.id)} />
        ))
      )}
      {misaligned && (
        <button type="button" className="realm-back role-ladder-save" onClick={() => commitOrder(staffOrder, true)}>
          Записать ранги
        </button>
      )}
      {floor.map((row) => (
        <RoleCard key={row.id} row={row} onOpen={() => setOpenId(row.id)} />
      ))}
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
  const owner = Number(row.rank) >= 5
  const rightsLocked = owner
  const tabsLocked = owner && !creator
  const reduce = useReducedMotion()
  const rights = new Set(row.rights || [])
  const pageIds = cabinetPagesFor(row)
  const dock = groupCabinetTabs(row.rights, false, pageIds, row.rank)
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
        owner
          ? 'Создатель группы. Права группы полные, снять их нельзя. Права на весь проект включаются отдельно внизу.'
          : row.kind === 'spamblock'
            ? 'Ранг 0. Права Telegram, этого чата и всего проекта включаете вы. Срок задаётся при назначении.'
            : Number(row.rank) <= 0 || row.kind === 'member'
              ? 'Ранг 0. Можно включить любые права: Telegram, этот чат и весь проект. Наказать можно человека без должности.'
              : `Ранг ${row.rank}. Сначала вкладки нижней полосы, потом права. Наказать можно только того, кто младше.`
      }
      onClose={onClose}
      footer={foot}
    >
      <fieldset className="realm-rights-block cabinet-tabs" disabled={tabsLocked}>
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
              disabled={tabsLocked}
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
        <fieldset className="realm-rights-block" disabled={rightsLocked}>
          <legend>Что видно в кабинете</legend>
          <p className="realm-copy">Это не наказание. Здесь только то, что должность видит в этой группе.</p>
          <RightList items={pages} rights={rights} locked={rightsLocked} onToggle={toggle} compareSet={compareSet} />
        </fieldset>
        <fieldset className="realm-rights-block" disabled={rightsLocked}>
          <legend>Наказания в этом чате</legend>
          <p className="realm-copy">Только эта группа. Включено — кнопка есть. Выключено — кнопки нет. Другие чаты эти права не трогают.</p>
          <RightList items={PUNISH_RIGHTS} rights={rights} locked={rightsLocked} onToggle={toggle} compareSet={compareSet} />
        </fieldset>
        <fieldset className="realm-rights-block" disabled={rightsLocked}>
          <legend>Права Telegram в чате</legend>
          <p className="realm-copy">Права внутри самого чата Telegram: удалять сообщения, звать людей, писать фото, стикеры и опросы.</p>
          <RightList
            items={TELEGRAM_ADMIN_RIGHTS}
            rights={rights}
            locked={rightsLocked}
            onToggle={toggle}
            compareSet={compareSet}
          />
        </fieldset>
        <fieldset className="realm-rights-block">
          <legend>Наказания шире этого чата</legend>
          <p className="realm-copy">
            Шире одной группы. Мут или бан в одном чате это не включает.
            Включено — кнопка есть. Выключено — её нет.
            {creator ? '' : ' Меняет только создатель проекта.'}
          </p>
          <RightList
            items={PROJECT_RIGHTS}
            rights={rights}
            locked={!creator}
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
