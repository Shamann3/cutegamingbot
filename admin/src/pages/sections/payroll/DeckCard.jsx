import { useEffect, useRef, useState } from 'react'
import PhotoLook from '../../../components/PhotoLook'
import { loadTgPhotoUrl } from '../../../components/TgPhoto'
import { fetchDeedPulse, getAdminToken, isPanelPreviewMode } from '../../../lib/adminClient'
import { pileLine } from '../../../lib/liveMerge'
import { issuerReason } from '../../../lib/deedSort'

export const FLY_MS = 420

export function when(iso) {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

export function duration(minutes) {
  if (minutes == null) return 'срок не указан'
  if (minutes >= 60 * 24 * 365) return 'навсегда'
  if (minutes >= 60 * 24) return `${Math.round(minutes / (60 * 24))} дн.`
  if (minutes >= 60) return `${Math.round(minutes / 60)} ч.`
  return `${minutes} мин.`
}

export function motionQuiet() {
  if (typeof window === 'undefined') return true
  if (document.body.classList.contains('perf-light')) return true
  return Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)
}

export function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

/** Следующее фото качается, пока человек смотрит текущую карточку. */
export function useWarmProof(fileId) {
  useEffect(() => {
    if (!fileId) return undefined
    loadTgPhotoUrl(fileId, 'full').catch(() => {})
    return undefined
  }, [fileId])
}

/** Пустая колода сама спрашивает новую карточку, не дёргая ту, что уже в руках. */
export function useRefill(queue, load) {
  useEffect(() => {
    if (!queue || queue.card) return undefined
    const timer = window.setTimeout(() => { load() }, 15000)
    return () => window.clearTimeout(timer)
  }, [queue, load])
}

const LIVE_MS = 2500

/** Карточка ещё не у этого человека: цепочку надо обновлять, саму карточку можно сменить. */
export function followsChain(stage, card) {
  if (!card?.turn) return false
  if (stage === 'queue') return card.turn !== 'creator'
  if (stage === 'staff') return card.turn === 'admin'
  return false
}

const deedListeners = new Set()
let deedSocket = null
let deedWait = null

function deedSocketUrl() {
  const token = getAdminToken()
  if (!token || typeof window === 'undefined') return ''
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const prefix = import.meta.env.VITE_ADMIN_API_PREFIX || '/admin/api'
  return `${proto}://${window.location.host}${prefix}/ws/moderation?token=${encodeURIComponent(token)}`
}

function ensureDeedSocket() {
  if (deedSocket || deedWait || typeof window === 'undefined') return
  const url = deedSocketUrl()
  if (!url) return
  const socket = new WebSocket(url)
  deedSocket = socket
  socket.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      if (msg?.event === 'new_moderation_log' || msg?.event === 'deed_chain') {
        deedListeners.forEach((fn) => fn())
      }
    } catch {
      /* чужой кадр */
    }
  }
  socket.onclose = () => {
    deedSocket = null
    if (deedListeners.size) {
      deedWait = window.setTimeout(() => {
        deedWait = null
        ensureDeedSocket()
      }, 2500)
    }
  }
}

function listenDeed(fn) {
  deedListeners.add(fn)
  ensureDeedSocket()
  return () => {
    deedListeners.delete(fn)
    if (deedListeners.size) return
    if (deedWait) {
      window.clearTimeout(deedWait)
      deedWait = null
    }
    if (deedSocket) {
      deedSocket.close()
      deedSocket = null
    }
  }
}

/**
 * Новое наказание само ложится в колоду.
 * Пустая колода открывает карточку. Карточку, которую уже можно решать, не подменяет.
 * Если очередь ещё у администратора или сотрудника, цепочка обновляется сама.
 * stage '' — чужой фильтр: пустую колоду обновляем, карточку в руках не трогаем.
 */
export function useDeckLive(stage, queue, setQueue, load) {
  const [pileNote, setPileNote] = useState('')
  const queueRef = useRef(queue)
  const loadRef = useRef(load)
  const lock = useRef(false)
  queueRef.current = queue
  loadRef.current = load

  useEffect(() => {
    if (!pileNote) return undefined
    const timer = window.setTimeout(() => setPileNote(''), 4600)
    return () => window.clearTimeout(timer)
  }, [pileNote])

  useEffect(() => {
    let stop = false
    const tick = async () => {
      if (stop || document.hidden || lock.current || isPanelPreviewMode()) return
      const snap = queueRef.current
      if (!snap) return
      lock.current = true
      try {
        if (!stage) {
          if (!snap.card) await loadRef.current()
          return
        }
        const data = await fetchDeedPulse()
        if (stop || data?.[stage] == null) return
        const waiting = Number(data[stage]) || 0
        const held = queueRef.current
        if (!held) return
        if (held.card) {
          if (followsChain(stage, held.card)) {
            await loadRef.current()
            return
          }
          const prev = Number(held.waiting) || 0
          if (waiting !== prev) {
            setQueue((current) => (current?.card ? { ...current, waiting } : current))
          }
          if (waiting > prev) setPileNote(pileLine(waiting - prev))
          return
        }
        if (waiting > 0) await loadRef.current()
      } catch {
        /* следующая сверка подберёт запись */
      } finally {
        lock.current = false
      }
    }
    const first = window.setTimeout(tick, 800)
    const timer = window.setInterval(tick, LIVE_MS)
    const unlisten = listenDeed(() => {
      const held = queueRef.current
      if (!held || lock.current) return
      if (!held.card || followsChain(stage, held.card)) {
        loadRef.current()
        return
      }
      tick()
    })
    return () => {
      stop = true
      window.clearTimeout(first)
      window.clearInterval(timer)
      unlisten()
    }
  }, [stage, setQueue])

  return pileNote
}

export function DeckPileNote({ text }) {
  if (!text) return null
  return <p className="deck-note deck-live" role="status">{text}</p>
}

let holdSeq = 0

function liveDeck() {
  for (const node of document.querySelectorAll('.deck-col')) {
    if (node instanceof HTMLElement && node.getClientRects().length) return node
  }
  return null
}

function fitHeight(col) {
  const box = col.getBoundingClientRect()
  let bottom = box.top
  for (const child of col.children) {
    const style = window.getComputedStyle(child)
    if (style.display === 'none' || style.position === 'fixed' || style.position === 'absolute') continue
    bottom = Math.max(bottom, child.getBoundingClientRect().bottom)
  }
  const own = window.getComputedStyle(col)
  return bottom - box.top + (parseFloat(own.paddingBottom) || 0) + (parseFloat(own.borderBottomWidth) || 0)
}

function scrollingBox(start) {
  for (let el = start instanceof Element ? start.parentElement : null; el; el = el.parentElement) {
    const y = window.getComputedStyle(el).overflowY
    if ((y === 'auto' || y === 'scroll' || y === 'overlay') && el.scrollHeight > el.clientHeight + 1) return el
  }
  const main = document.querySelector('.panel-shell-main')
  if (main instanceof HTMLElement) return main
  return document.scrollingElement || document.documentElement
}

/**
 * Пока карточка меняется, вкладка остаётся на том же месте.
 * Рост колоды держат до конца смены, а положение поправляют каждый кадр:
 * иначе страница уезжает вверх, когда карточка короче, и возвращается вниз.
 */
export function pinShellScroll() {
  const col = liveDeck()
  const box = scrollingBox(col)
  const html = document.documentElement
  const prevHtml = html.style.scrollBehavior
  const prevBox = box.style.scrollBehavior
  html.classList.add('deck-scroll-lock')
  html.style.scrollBehavior = 'auto'
  box.style.scrollBehavior = 'auto'
  const seq = ++holdSeq
  const tall = col ? Math.ceil(col.getBoundingClientRect().height) : 0
  let anchor = col ? col.getBoundingClientRect().top : null
  const saved = box.scrollTop
  if (tall > 0 && col) {
    col.style.transition = 'none'
    col.style.minHeight = `${tall}px`
  }
  const focused = document.activeElement
  if (focused instanceof HTMLElement && focused !== document.body && col?.contains(focused)) focused.blur()

  let alive = true
  let userUntil = 0
  const onUser = () => {
    userUntil = performance.now() + 140
  }
  box.addEventListener('wheel', onUser, { passive: true })
  box.addEventListener('touchmove', onUser, { passive: true })
  const stopListen = () => {
    box.removeEventListener('wheel', onUser)
    box.removeEventListener('touchmove', onUser)
  }
  const place = () => {
    if (seq !== holdSeq) return
    if (performance.now() < userUntil) {
      if (col?.isConnected) anchor = col.getBoundingClientRect().top
      return
    }
    if (col?.isConnected && anchor != null) {
      const drift = col.getBoundingClientRect().top - anchor
      if (Math.abs(drift) > 1) box.scrollTop += drift
      return
    }
    if (Math.abs(box.scrollTop - saved) > 1) box.scrollTop = saved
  }
  const loop = () => {
    if (seq !== holdSeq) {
      stopListen()
      return
    }
    if (!alive) return
    place()
    window.requestAnimationFrame(loop)
  }
  window.requestAnimationFrame(loop)

  const unlock = () => {
    if (seq !== holdSeq) return
    alive = false
    stopListen()
    html.style.scrollBehavior = prevHtml
    box.style.scrollBehavior = prevBox
    html.classList.remove('deck-scroll-lock')
  }
  let released = false
  return () => {
    if (released || seq !== holdSeq) return
    released = true
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        if (seq !== holdSeq) return
        if (col?.isConnected) {
          col.style.transition = 'none'
          const fit = Math.floor(fitHeight(col))
          col.style.minHeight = fit > 0 ? `${fit}px` : ''
        }
        place()
        window.requestAnimationFrame(() => {
          if (seq !== holdSeq) return
          if (col?.isConnected) {
            col.style.minHeight = ''
            col.style.transition = ''
          }
          place()
          window.requestAnimationFrame(() => {
            if (seq !== holdSeq) return
            place()
            unlock()
          })
        })
      })
    })
  }
}

export function useToastInView() {
  return useRef(null)
}

function stepWord(step) {
  if (step.role === 'issue') return step.name || 'готово'
  if (step.state === 'done') return (step.label || 'ответил').toLowerCase()
  if (step.state === 'now') return 'сейчас'
  if (step.state === 'skip') return 'можно не ждать'
  return 'следом'
}

export default function DeckCard({ card, band, tone = '', note = '', stamps, depth = 0, fly = '', back = '', swipe }) {
  const place = [card.chatTitle, card.scopeLabel].filter(Boolean).join(' · ')
  const issued = (card.process || []).find((step) => step.role === 'issue')
  const issuer = issued?.title
    ? `${issued.title} ${card.adminName || ''}`.trim()
    : (card.adminName || 'администратор')
  const spoken = issuerReason(card.reason)
  const speaker = card.adminName || 'Администратор'
  const motion = fly ? ` is-fly-${fly}` : back ? ` is-back-${back}` : ''
  return (
    <div ref={swipe.stageRef} className={`tinder-stage depth-${depth}${fly ? ' is-flying' : ''}`} {...swipe.handlers}>
      {depth > 0 && <div className="tinder-plate" aria-hidden="true" />}
      <div ref={swipe.dragRef} key={card.id} className={`tinder-drag${motion}`}>
        <article className="staff-member-row deed-card tinder-card">
          {stamps.map((stamp) => (
            <span key={stamp.side} className={`tinder-stamp is-${stamp.side}`} aria-hidden="true">
              {stamp.label}
            </span>
          ))}
          <div className="deed-why">
            <p className="deed-why-kicker">Причина наказания</p>
            {spoken
              ? <p className="deed-reason">{spoken}</p>
              : <p className="deed-reason is-empty">{speaker} не записал причину. Смотрите фото, срок и само наказание.</p>}
            <p className="deed-why-note">
              {spoken
                ? `Записал: ${speaker}. Сверьте эти слова с фото и со сроком.`
                : 'Дальше на карточке фото, срок и какое это наказание.'}
            </p>
          </div>
          <div className="deed-face">
            {card.hasProof && card.proofMediaId
              ? <PhotoLook fileId={card.proofMediaId} eager alt="Фото доказательства" />
              : (
                <div className="deed-photo deed-photo-empty">
                  <strong>{card.actionLabel}</strong>
                  <span>Фото к этому наказанию нет.</span>
                </div>
              )}
          </div>
          <div className="deed-copy">
            <p className={`work-band${tone ? ` is-${tone}` : ''}`}>
              <i aria-hidden="true" />
              {band}
            </p>
            {note && <p className="deck-note">{note}</p>}
            <h3 className="staff-card-name">{card.actionLabel} · {card.targetName || 'игрок'}</h3>
            <p className="staff-card-date">
              Выдал {issuer} · {when(card.createdAt)} · {duration(card.durationMinutes)}
              {place ? ` · ${place}` : ''}
            </p>
            {(card.process || []).length > 0 && (
              <ol className="deed-process">
                {card.process.map((step) => (
                  <li key={step.role} className={`is-${step.state || 'later'}`}>
                    <span>{step.title}</span>
                    <small>{stepWord(step)}</small>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </article>
      </div>
    </div>
  )
}
