import { useRef, useState } from 'react'
import { RARITY_ACCENT, RARITY_LABEL } from '../constants/giveaways'

const SWIPE_THRESHOLD = 90

export default function GiveawayTicketCard({ giveaway, onOpenDetail, onSwipeParticipate }) {
  const [dragX, setDragX] = useState(0)
  const [swiping, setSwiping] = useState(false)
  const dragRef = useRef({ startX: 0, tracking: false })
  const accent = RARITY_ACCENT[giveaway.rarity] ?? RARITY_ACCENT.common

  const canSwipe = giveaway.status === 'active' && !giveaway.joined
    && (giveaway.conditionsCount === 0 || giveaway.conditionsMet)

  const onTouchStart = (event) => {
    if (!canSwipe) return
    dragRef.current = { startX: event.touches[0].clientX, tracking: true }
  }

  const onTouchMove = (event) => {
    if (!dragRef.current.tracking) return
    const dx = event.touches[0].clientX - dragRef.current.startX
    setDragX(Math.max(0, dx))
  }

  const onTouchEnd = async () => {
    if (!dragRef.current.tracking) return
    dragRef.current.tracking = false
    if (dragX >= SWIPE_THRESHOLD) {
      setSwiping(true)
      const ok = await onSwipeParticipate(giveaway.id)
      setSwiping(false)
      if (!ok) setDragX(0)
    } else {
      setDragX(0)
    }
  }

  let statusLabel = null
  if (giveaway.status === 'completed') {
    statusLabel = giveaway.won ? '🏆 Вы выиграли!' : 'Розыгрыш завершён'
  } else if (giveaway.status === 'cancelled') {
    statusLabel = 'Розыгрыш отменён'
  } else if (giveaway.joined) {
    statusLabel = giveaway.drawType === 'instant' ? '✅ Приз получен' : '🎟️ Вы в розыгрыше'
  }

  return (
    <button
      type="button"
      data-no-swipe
      className={`giveaway-ticket giveaway-ticket--${giveaway.rarity}${swiping ? ' giveaway-ticket--swiping' : ''}`}
      style={{
        '--ticket-accent-strong': accent.strong,
        '--ticket-accent-glow': accent.glow,
        transform: dragX ? `translateX(${dragX}px)` : undefined,
      }}
      onClick={() => { if (!dragX) onOpenDetail(giveaway.id) }}
      onTouchStart={onTouchStart}
      onTouchMove={onTouchMove}
      onTouchEnd={onTouchEnd}
    >
      <span className="giveaway-ticket-rarity">{RARITY_LABEL[giveaway.rarity] ?? giveaway.rarity}</span>
      <span className="giveaway-ticket-emoji" aria-hidden>{giveaway.emoji}</span>
      <span className="giveaway-ticket-title">{giveaway.title}</span>
      {statusLabel && <span className="giveaway-ticket-status">{statusLabel}</span>}
      {canSwipe && !statusLabel && (
        <span className="giveaway-ticket-swipe-hint">Смахните →</span>
      )}
    </button>
  )
}
