import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import FocusWindow from './FocusWindow'
import { fetchRightsBoard, pushGroupPositions } from '../lib/adminClient'
import { ruCount } from '../lib/panelPreview'
import {
  planPush,
  pushDetail,
  pushNotice,
  pushReceiptLines,
  pushShiftLine,
  pushStateLabel,
} from '../lib/positionPush'
import { positionOrder } from '../lib/rankLadder'

const EVERY = '*'
const EDGE = 64
const EASE = [0.22, 1, 0.36, 1]

function rankCaption(row) {
  if (row.kind === 'spamblock') return 'спам-блок · ранг 0'
  if (row.kind === 'member') return 'участник · ранг 0'
  return `ранг ${row.rank}`
}

function holdersOf(group) {
  const out = new Map()
  for (const seat of group?.seats || []) {
    const id = Number(seat.positionId)
    out.set(id, (out.get(id) || 0) + 1)
  }
  return out
}

/** Своё перетаскивание: мышь, палец за ручку и перо. У края окна список сам едет. */
function usePushDrag(onDrop) {
  const [drag, setDrag] = useState(null)
  const [over, setOver] = useState(null)
  const ghostRef = useRef(null)
  const live = useRef(null)
  const dropRef = useRef(onDrop)

  useEffect(() => {
    dropRef.current = onDrop
  })

  const finish = useCallback((commit) => {
    const session = live.current
    if (!session) return
    live.current = null
    window.removeEventListener('pointermove', session.move)
    window.removeEventListener('pointerup', session.up)
    window.removeEventListener('pointercancel', session.cancel)
    window.removeEventListener('keydown', session.key, true)
    if (session.frame) window.cancelAnimationFrame?.(session.frame)
    if (!session.started) return
    document.documentElement.classList.remove('is-push-dragging')
    // Отпустили над затемнением — клик после отпускания не должен закрыть окно.
    const swallow = (event) => {
      event.stopPropagation()
      event.preventDefault()
    }
    window.addEventListener('click', swallow, { capture: true, once: true })
    window.setTimeout(() => window.removeEventListener('click', swallow, true), 0)
    setDrag(null)
    setOver(null)
    if (commit && session.over) dropRef.current?.(session.over, session.ids)
  }, [])

  useEffect(() => () => finish(false), [finish])

  const press = useCallback((event, ids, label) => {
    if (event.button !== undefined && event.button !== 0) return
    finish(false)
    const session = {
      ids,
      label,
      pointerId: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      x0: event.clientX,
      y0: event.clientY,
      started: false,
      over: null,
      frame: 0,
      scroller: event.currentTarget.closest('.focus-sheet-body'),
    }
    const paint = () => {
      const ghost = ghostRef.current
      if (ghost) ghost.style.transform = `translate3d(${session.x + 12}px, ${session.y + 12}px, 0)`
    }
    const hit = () => {
      const node = document.elementFromPoint?.(session.x, session.y)
      const zone = node?.closest?.('[data-push-zone]')
      const next = zone ? zone.getAttribute('data-push-zone') : null
      if (next !== session.over) {
        session.over = next
        setOver(next)
      }
    }
    const tick = () => {
      session.frame = 0
      const box = session.scroller?.getBoundingClientRect?.()
      if (!box) return
      let speed = 0
      if (session.y < box.top + EDGE) speed = -Math.ceil((box.top + EDGE - session.y) / 5)
      else if (session.y > box.bottom - EDGE) speed = Math.ceil((session.y - (box.bottom - EDGE)) / 5)
      if (!speed) return
      session.scroller.scrollTop += speed
      hit()
      session.frame = window.requestAnimationFrame?.(tick) || 0
    }
    session.move = (moveEvent) => {
      if (moveEvent.pointerId !== session.pointerId) return
      session.x = moveEvent.clientX
      session.y = moveEvent.clientY
      if (!session.started) {
        if (Math.hypot(session.x - session.x0, session.y - session.y0) < 6) return
        session.started = true
        document.documentElement.classList.add('is-push-dragging')
        setDrag({ ids, label, x: session.x, y: session.y })
      }
      if (moveEvent.cancelable) moveEvent.preventDefault()
      paint()
      hit()
      if (!session.frame) session.frame = window.requestAnimationFrame?.(tick) || 0
    }
    session.up = (upEvent) => {
      if (upEvent.pointerId === session.pointerId) finish(true)
    }
    session.cancel = (cancelEvent) => {
      if (cancelEvent.pointerId === session.pointerId) finish(false)
    }
    session.key = (keyEvent) => {
      if (keyEvent.key !== 'Escape' || !session.started) return
      keyEvent.stopPropagation()
      keyEvent.preventDefault()
      finish(false)
    }
    live.current = session
    window.addEventListener('pointermove', session.move, { passive: false })
    window.addEventListener('pointerup', session.up)
    window.addEventListener('pointercancel', session.cancel)
    window.addEventListener('keydown', session.key, true)
  }, [finish])

  return { drag, over, ghostRef, press }
}

function PlanLine({ item, holders, groupTitle, onRemove, reduce }) {
  const detail = pushDetail(item, holders)
  return (
    <motion.li
      layout={reduce ? false : 'position'}
      className={`push-line is-${item.state}`}
      initial={reduce ? false : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={reduce ? { opacity: 0 } : { opacity: 0, y: -4 }}
      transition={{ duration: reduce ? 0 : 0.2, ease: EASE }}
    >
      <div className="push-line-text">
        <div className="push-line-top">
          <strong>{item.title}</strong>
          <span className={`push-state is-${item.state}`}>{pushStateLabel(item)}</span>
        </div>
        {detail.map((line) => <span key={line} className="push-line-detail">{line}</span>)}
      </div>
      <button
        type="button"
        className="push-line-drop"
        aria-label={`Не переносить «${item.title}» в ${groupTitle}`}
        onClick={() => onRemove(item.sourceId)}
      >
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>
    </motion.li>
  )
}

export default function PositionPush({ chatId, onClose }) {
  const reduce = useReducedMotion()
  const [groups, setGroups] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [selected, setSelected] = useState(() => new Set())
  const [plan, setPlan] = useState({})
  const [query, setQuery] = useState('')
  const [receipt, setReceipt] = useState(null)
  const [landed, setLanded] = useState(() => new Set())
  const [announce, setAnnounce] = useState('')
  const noticeRef = useRef('')
  const landTimer = useRef(0)

  useEffect(() => {
    let stop = false
    fetchRightsBoard()
      .then((board) => {
        if (!stop) setGroups(board.groups || [])
      })
      .catch((err) => {
        if (stop) return
        setGroups([])
        setError(err.message || 'Список групп не открылся')
      })
    return () => {
      stop = true
    }
  }, [])

  useEffect(() => () => window.clearTimeout(landTimer.current), [])

  const source = (groups || []).find((group) => Number(group.chatId) === Number(chatId)) || null
  const tokens = useMemo(
    () => positionOrder(source?.positions || []).filter((row) => Number(row.rank) < 5),
    [source],
  )
  const place = useMemo(() => new Map(tokens.map((row, index) => [Number(row.id), index])), [tokens])
  const targets = useMemo(
    () => (groups || []).filter((group) => Number(group.chatId) !== Number(chatId)),
    [groups, chatId],
  )
  const needle = query.trim().toLowerCase()
  const shown = needle
    ? targets.filter((group) => String(group.title || '').toLowerCase().includes(needle))
    : targets

  const previews = useMemo(() => {
    const out = new Map()
    for (const group of targets) {
      const key = String(group.chatId)
      const ids = plan[key] || []
      if (!ids.length) continue
      out.set(key, planPush({ source: source?.positions || [], target: group.positions || [], ids }))
    }
    return out
  }, [targets, plan, source])

  const ready = targets.filter((group) => previews.get(String(group.chatId))?.changed)
  const changeCount = ready.reduce(
    (sum, group) => sum + previews.get(String(group.chatId)).items.filter((item) => item.state === 'new' || item.state === 'update').length,
    0,
  )
  const planned = Object.values(plan).some((ids) => ids.length)
  const picked = tokens.filter((row) => selected.has(Number(row.id))).map((row) => Number(row.id))

  const addTo = useCallback((key, ids) => {
    const clean = [...new Set(ids.map(Number))].filter((id) => place.has(id))
    if (!clean.length) return
    const keys = key === EVERY ? targets.map((group) => String(group.chatId)) : [String(key)]
    if (!keys.length) return
    setPlan((current) => {
      const next = { ...current }
      for (const item of keys) {
        const merged = new Set([...(next[item] || []), ...clean])
        next[item] = [...merged].sort((a, b) => place.get(a) - place.get(b))
      }
      return next
    })
    setReceipt(null)
    setError('')
    window.clearTimeout(landTimer.current)
    setLanded(new Set(key === EVERY ? [EVERY, ...keys] : keys))
    landTimer.current = window.setTimeout(() => setLanded(new Set()), 600)
    const first = tokens.find((row) => Number(row.id) === clean[0])
    const what = clean.length === 1 ? `«${first?.title || 'Должность'}»` : ruCount(clean.length, 'должность', 'должности', 'должностей')
    const where = key === EVERY ? 'во все группы' : `в ${targets.find((group) => String(group.chatId) === String(key))?.title || 'группу'}`
    setAnnounce(`${what} — ${where}`)
  }, [place, targets, tokens])

  const { drag, over, ghostRef, press } = usePushDrag(addTo)

  const toggle = (id) => {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const allPicked = tokens.length > 0 && picked.length === tokens.length
  const pickAll = () => {
    setSelected(allPicked ? new Set() : new Set(tokens.map((row) => Number(row.id))))
  }

  const grabbed = (row) => {
    const id = Number(row.id)
    if (selected.has(id) && picked.length > 1) return picked
    return [id]
  }

  const removeFrom = (key, sourceId) => {
    setPlan((current) => ({ ...current, [key]: (current[key] || []).filter((id) => id !== Number(sourceId)) }))
  }

  const clearZone = (key) => {
    setPlan((current) => ({ ...current, [key]: [] }))
  }

  const close = () => onClose?.(noticeRef.current)

  const apply = async () => {
    const body = {
      source_chat_id: Number(chatId),
      targets: ready.map((group) => ({ chat_id: Number(group.chatId), ids: plan[String(group.chatId)] })),
    }
    if (!body.targets.length) return
    setBusy(true)
    setError('')
    try {
      const data = await pushGroupPositions(body)
      const results = (data?.groups || []).map((group) => ({
        ...group,
        title: targets.find((item) => Number(item.chatId) === Number(group.chatId))?.title || group.title,
      }))
      setReceipt(results)
      noticeRef.current = pushNotice(results)
      setPlan((current) => {
        const next = { ...current }
        for (const group of results) {
          if (!group.error) delete next[String(group.chatId)]
        }
        return next
      })
      try {
        const board = await fetchRightsBoard()
        setGroups(board.groups || [])
      } catch {
        /* превью пересчитается при следующем открытии */
      }
    } catch (err) {
      setError(err.message || 'Должности не перенеслись')
    } finally {
      setBusy(false)
    }
  }

  const footLabel = busy
    ? 'Переносим…'
    : ready.length
      ? `Перенести в ${ruCount(ready.length, 'группу', 'группы', 'групп')} · ${ruCount(changeCount, 'изменение', 'изменения', 'изменений')}`
      : receipt
        ? 'Готово'
        : planned
          ? 'Менять нечего: там всё как здесь'
          : 'Перенести'
  const footAction = ready.length ? apply : (receipt ? close : undefined)

  const addLabel = picked.length ? `Сюда · ${picked.length}` : 'Всё сюда'
  const addIds = () => (picked.length ? picked : tokens.map((row) => Number(row.id)))
  const dragging = Boolean(drag)
  const dragText = drag ? (drag.ids.length > 1 ? ruCount(drag.ids.length, 'должность', 'должности', 'должностей') : `«${drag.label}»`) : ''

  return (
    <FocusWindow
      wide
      title="В другие группы"
      subtitle="Перетащите должность на группу — там она станет как здесь: права, вкладки, префикс и место в лестнице. Люди остаются на своих местах."
      onClose={close}
      footer={(
        <button type="button" className="sec-btn is-on" disabled={busy || !footAction} onClick={footAction}>
          {footLabel}
        </button>
      )}
    >
      <p className="sr-only" aria-live="polite">{announce}</p>
      {error && <p className="realm-alert" role="alert">{error}</p>}
      {receipt && (
        <section className="push-receipt" role="status">
          <h3>Перенос записан</h3>
          <ul>
            {receipt.map((group) => (
              <li key={group.chatId} className={group.error ? 'is-bad' : ''}>
                <strong>{group.title}</strong>
                {pushReceiptLines(group).map((line) => <span key={line}>{line}</span>)}
              </li>
            ))}
          </ul>
        </section>
      )}
      {groups === null && <p className="realm-copy">Группы открываются…</p>}
      {groups !== null && !source && !error && (
        <p className="realm-copy">Этой группы нет среди официальных — переносить отсюда нечего.</p>
      )}
      {source && (
        <div className={`push-board${dragging ? ' is-dragging' : ''}`}>
          <section className="push-tray" aria-labelledby="push-tray-title">
            <header className="push-head">
              <div>
                <h3 id="push-tray-title">Отсюда</h3>
                <p>{source.title}</p>
              </div>
              {tokens.length > 0 && (
                <button type="button" className="push-link" onClick={pickAll}>
                  {allPicked ? 'Снять выбор' : 'Выбрать все'}
                </button>
              )}
            </header>
            {tokens.length > 0 ? (
              <ul className="push-tokens">
                {tokens.map((row) => {
                  const id = Number(row.id)
                  const on = selected.has(id)
                  const lifted = Boolean(drag?.ids.includes(id))
                  return (
                    <li key={id}>
                      <button
                        type="button"
                        className={`push-token${on ? ' is-on' : ''}${lifted ? ' is-lifted' : ''}`}
                        aria-pressed={on}
                        aria-label={`${row.title}, ${rankCaption(row)}`}
                        onPointerDown={(event) => {
                          const viaGrip = Boolean(event.target.closest?.('.push-token-grip'))
                          if (event.pointerType === 'mouse' || viaGrip) press(event, grabbed(row), row.title)
                        }}
                        onClick={() => toggle(id)}
                      >
                        <span className="push-token-grip" aria-hidden="true"><i /></span>
                        <span className="push-token-text">
                          <strong>{row.title}</strong>
                          <span>{rankCaption(row)}</span>
                        </span>
                        <span className="push-token-check" aria-hidden="true">
                          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M5 12.5l4.2 4.2L19 7" />
                          </svg>
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            ) : (
              <p className="realm-copy">Здесь нет должностей, кроме создателя группы.</p>
            )}
            <p className="push-tray-note">Создатель группы не переносится: в каждой группе он свой. Тяните за точки слева или выберите должности и нажмите «Сюда» у группы.</p>
          </section>

          <section className="push-targets" aria-labelledby="push-targets-title">
            <header className="push-head">
              <div>
                <h3 id="push-targets-title">Куда</h3>
                <p>{targets.length ? ruCount(targets.length, 'официальная группа', 'официальные группы', 'официальных групп') : 'других групп нет'}</p>
              </div>
            </header>
            {!targets.length && (
              <p className="realm-copy">Других официальных групп нет. Их добавляют во вкладке «Группы».</p>
            )}
            {targets.length > 1 && tokens.length > 0 && (
              <div
                className={`push-zone is-every${over === EVERY ? ' is-over' : ''}${landed.has(EVERY) ? ' is-landed' : ''}`}
                data-push-zone={EVERY}
              >
                <div className="push-zone-head">
                  <div className="push-zone-name">
                    <strong>Во все группы</strong>
                    <span>{over === EVERY ? `Отпустите — ${dragText} ляжет в каждую` : ruCount(targets.length, 'группа', 'группы', 'групп')}</span>
                  </div>
                  <button
                    type="button"
                    className={`push-zone-add${picked.length ? ' is-pick' : ''}`}
                    onClick={() => addTo(EVERY, addIds())}
                  >
                    {addLabel}
                  </button>
                </div>
              </div>
            )}
            {targets.length > 6 && (
              <label className="realm-field push-find">Найти группу
                <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Название" />
              </label>
            )}
            <ul className="push-zones">
              {shown.map((group) => {
                const key = String(group.chatId)
                const preview = previews.get(key)
                const holders = holdersOf(group)
                const people = (group.seats || []).length
                const count = (group.positions || []).length
                return (
                  <li
                    key={key}
                    className={`push-zone${over === key ? ' is-over' : ''}${landed.has(key) ? ' is-landed' : ''}`}
                    data-push-zone={key}
                  >
                    <div className="push-zone-head">
                      <div className="push-zone-name">
                        <strong>{group.title}</strong>
                        <span>
                          {ruCount(count, 'должность', 'должности', 'должностей')}
                          {people > 0 ? ` · ${ruCount(people, 'человек', 'человека', 'человек')} на местах` : ''}
                        </span>
                      </div>
                      {tokens.length > 0 && (
                        <button
                          type="button"
                          className={`push-zone-add${picked.length ? ' is-pick' : ''}`}
                          aria-label={`${addLabel} — ${group.title}`}
                          onClick={() => addTo(key, addIds())}
                        >
                          {addLabel}
                        </button>
                      )}
                    </div>
                    {preview?.items.length ? (
                      <>
                        <ul className="push-lines">
                          <AnimatePresence initial={false}>
                            {preview.items.map((item) => (
                              <PlanLine
                                key={item.sourceId}
                                item={item}
                                holders={holders.get(Number(item.targetId)) || 0}
                                groupTitle={group.title}
                                onRemove={(sourceId) => removeFrom(key, sourceId)}
                                reduce={reduce}
                              />
                            ))}
                          </AnimatePresence>
                        </ul>
                        {preview.shifts.length > 0 && <p className="push-zone-shift">{pushShiftLine(preview.shifts)}</p>}
                        <div className="push-zone-foot">
                          <button type="button" className="push-link" onClick={() => clearZone(key)}>Убрать всё</button>
                        </div>
                      </>
                    ) : (
                      <p className="push-zone-empty">
                        {over === key ? `Отпустите — ${dragText} ляжет сюда` : 'Сюда пока ничего не переносится'}
                      </p>
                    )}
                  </li>
                )
              })}
            </ul>
            {needle && !shown.length && <p className="realm-copy">Такой группы нет.</p>}
          </section>
        </div>
      )}
      {drag && createPortal(
        <div
          ref={ghostRef}
          className="push-ghost"
          aria-hidden="true"
          style={{ transform: `translate3d(${drag.x + 12}px, ${drag.y + 12}px, 0)` }}
        >
          <span className="push-ghost-body">
            <i />
            <strong>{drag.label}</strong>
            {drag.ids.length > 1 && <b>+{drag.ids.length - 1}</b>}
          </span>
        </div>,
        document.body,
      )}
    </FocusWindow>
  )
}
