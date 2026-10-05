import { useEffect, useRef, useState } from 'react'
import PhotoLook from '../../../components/PhotoLook'
import { loadTgPhotoUrl } from '../../../components/TgPhoto'
import { fetchDeedPulse, isPanelPreviewMode } from '../../../lib/adminClient'
import { pileLine } from '../../../lib/liveMerge'

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

/**
 * Новое наказание само ложится в колоду.
 * Пустая колода открывает карточку. Открытую карточку не подменяет — только число за ней.
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
    return () => {
      stop = true
      window.clearTimeout(first)
      window.clearInterval(timer)
    }
  }, [stage, setQueue])

  return pileNote
}

export function DeckPileNote({ text }) {
  if (!text) return null
  return <p className="deck-note deck-live" role="status">{text}</p>
}

/** После ответа карточка меняется, а экран остаётся на месте. */
export function pinShellScroll() {
  const main = document.querySelector('.panel-shell-main')
  const top = main instanceof HTMLElement ? main.scrollTop : 0
  const y = window.scrollY
  const restore = () => {
    if (main instanceof HTMLElement) main.scrollTop = top
    if (window.scrollY !== y) window.scrollTo(0, y)
  }
  return () => {
    restore()
    window.requestAnimationFrame(restore)
  }
}

export function useToastInView() {
  return useRef(null)
}

export default function DeckCard({ card, band, tone = '', note = '', stamps, depth = 0, fly = '', back = '', swipe }) {
  const place = [card.chatTitle, card.scopeLabel].filter(Boolean).join(' · ')
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
          <div className="deed-face">
            {card.hasProof && card.proofMediaId
              ? <PhotoLook fileId={card.proofMediaId} eager alt="Фото доказательства" />
              : (
                <div className="deed-photo deed-photo-empty">
                  <strong>{card.actionLabel}</strong>
                  <span>{card.reason ? 'Фото нет — смотрите причину ниже.' : 'Ни фото, ни причины не записано.'}</span>
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
              Выдал {card.adminName || 'администратор'} · {when(card.createdAt)} · {duration(card.durationMinutes)}
              {place ? ` · ${place}` : ''}
            </p>
            <p className="deed-reason">{card.reason || 'Причина в архиве не записана'}</p>
          </div>
        </article>
      </div>
    </div>
  )
}
