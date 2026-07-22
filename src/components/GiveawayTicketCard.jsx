import { useRef, useState } from 'react'
import { RARITY_ACCENT, RARITY_LABEL, formatGiveawayDeadline, formatGiveawayPrize } from '../constants/giveaways'

const SWIPE_THRESHOLD = 90

function initial(name) {
  const clean = name.replace(/^@/, '')
  return clean.charAt(0).toUpperCase() || '?'
}

export default function GiveawayTicketCard({ giveaway, onOpenDetail, onSwipeParticipate }) {
  const [dragX, setDragX] = useState(0)
  const [swiping, setSwiping] = useState(false)
  const dragRef = useRef({ startX: 0, tracking: false })
  const accent = RARITY_ACCENT[giveaway.rarity] ?? RARITY_ACCENT.common
  const isLegendary = giveaway.rarity === 'legendary'
  const isUpcoming = Boolean(giveaway.startsAt) && new Date(giveaway.startsAt).getTime() > Date.now()

  const canSwipe = giveaway.status === 'active' && !giveaway.joined && !isUpcoming
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
      await onSwipeParticipate(giveaway.id)
      setSwiping(false)
      setDragX(0)
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

  const deadline = !isUpcoming && giveaway.drawType === 'timer' ? formatGiveawayDeadline(giveaway.endsAt) : null
  const startLabel = isUpcoming ? formatGiveawayDeadline(giveaway.startsAt) : null
  const isInstant = !isUpcoming && giveaway.drawType === 'instant'
  const prizeLabel = formatGiveawayPrize(giveaway.prize)
  const serial = `№ ${String(giveaway.id).padStart(4, '0')}`

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
      {isLegendary && <span className="giveaway-ticket-legendary-badge">Легендарный</span>}
      <span className="giveaway-ticket-notch giveaway-ticket-notch--top" aria-hidden />
      <span className="giveaway-ticket-notch giveaway-ticket-notch--bottom" aria-hidden />

      <div className="giveaway-ticket-stub">
        <span className="giveaway-ticket-emoji" aria-hidden>{giveaway.emoji}</span>
        <span className="giveaway-ticket-serial">{serial}</span>
      </div>

      <div className="giveaway-ticket-body">
        <span className="giveaway-ticket-rarity">{RARITY_LABEL[giveaway.rarity] ?? giveaway.rarity}</span>
        <span className="giveaway-ticket-title">{giveaway.title}</span>
        <span className="giveaway-ticket-prize">{prizeLabel}</span>

        {(startLabel || deadline || isInstant) && (
          <div className="giveaway-ticket-meta">
            {startLabel && <span className="giveaway-chip">🚀 Старт {startLabel}</span>}
            {deadline && <span className="giveaway-chip">⏳ До {deadline}</span>}
            {isInstant && <span className="giveaway-chip">⚡ Мгновенно всем</span>}
          </div>
        )}

        <div className="giveaway-ticket-foot">
          {giveaway.participantsCount > 0 ? (
            <div className="giveaway-ticket-participants">
              <div className="giveaway-ticket-avatars">
                {(giveaway.participantsPreview ?? []).slice(0, 4).map((name, i) => (
                  <span key={i} className="giveaway-ticket-avatar">{initial(name)}</span>
                ))}
              </div>
              <span className="giveaway-ticket-participants-count">👥 {giveaway.participantsCount}</span>
            </div>
          ) : <span />}

          {statusLabel ? (
            <span className="giveaway-ticket-status">{statusLabel}</span>
          ) : canSwipe ? (
            <span className="giveaway-ticket-swipe-hint">Смахните <span className="giveaway-swipe-arrow">→</span></span>
          ) : isUpcoming ? (
            <span className="giveaway-ticket-swipe-hint">⏳ Скоро</span>
          ) : null}
        </div>
      </div>
    </button>
  )
}
