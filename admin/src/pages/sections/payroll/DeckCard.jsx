import { useEffect, useRef } from 'react'
import PhotoLook from '../../../components/PhotoLook'

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

/** Сообщение под кнопками докручивается в кадр, если ушло под нижнее меню телефона. */
export function useToastInView(flashKey) {
  const ref = useRef(null)
  useEffect(() => {
    if (!flashKey) return
    ref.current?.scrollIntoView?.({ block: 'nearest', behavior: motionQuiet() ? 'auto' : 'smooth' })
  }, [flashKey])
  return ref
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
