import { useRef, useState } from 'react'
import {
  RARITY_ACCENT,
  RARITY_LABEL,
  formatCountdown,
  formatGiveawayPrize,
  isEndingSoon,
  isDrawToday,
} from '../constants/giveaways'
import { useNow } from '../hooks/useNow'

const SWIPE_THRESHOLD = 90
const POPULAR_THRESHOLD = 50
const NEW_WINDOW_MS = 48 * 3600 * 1000

export default function GiveawayTicketCard({ giveaway, onOpenDetail, onSwipeParticipate }) {
  const now = useNow()
  const [dragX, setDragX] = useState(0)
  const [swiping, setSwiping] = useState(false)
  const dragRef = useRef({ startX: 0, tracking: false })

  const accent = RARITY_ACCENT[giveaway.rarity] ?? RARITY_ACCENT.common
  const isLegendary = giveaway.rarity === 'legendary'
  const isTimer = giveaway.drawType === 'timer'
  const startsMs = giveaway.startsAt ? new Date(giveaway.startsAt).getTime() : null
  const isUpcoming = startsMs != null && startsMs > now
  const isCompleted = giveaway.status === 'completed'
  const isCancelled = giveaway.status === 'cancelled'
  const conditionsDone = giveaway.conditionsCount === 0 || giveaway.conditionsMet

  const canSwipe = giveaway.status === 'active' && !giveaway.joined && !isUpcoming && conditionsDone

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

  // Живой таймер: до старта (анонс) или до конца (розыгрыш по таймеру).
  const countdownTarget = isUpcoming ? giveaway.startsAt : isTimer ? giveaway.endsAt : null
  const countdown = !isCompleted && !isCancelled ? formatCountdown(countdownTarget, now) : null
  const urgent = !isUpcoming && !isCompleted && isEndingSoon(giveaway.endsAt, now)

  // Бейджи — максимум 2, чтобы не перегружать карточку.
  const badges = []
  if (isLegendary) badges.push({ key: 'legendary', mod: 'legendary', text: '💎 Легендарный' })
  if (!isCompleted && !isUpcoming && isTimer && isDrawToday(giveaway.endsAt, now)) {
    badges.push({ key: 'today', mod: 'soon', text: '🎉 Сегодня' })
  } else if (!isCompleted && urgent) {
    badges.push({ key: 'soon', mod: 'soon', text: '⏳ Скоро завершится' })
  }
  if (!isCompleted && (giveaway.participantsCount ?? 0) >= POPULAR_THRESHOLD) {
    badges.push({ key: 'hot', mod: 'hot', text: '🔥 Популярный' })
  }
  const isNew = giveaway.createdAt && now - new Date(giveaway.createdAt).getTime() <= NEW_WINDOW_MS
  if (isNew && !isCompleted && !isUpcoming) badges.push({ key: 'new', mod: 'new', text: '⭐ Новый' })
  const shownBadges = badges.slice(0, 2)

  // Статус участия.
  let status
  if (isCompleted) {
    status = giveaway.won
      ? { tone: 'win', text: '🏆 Вы выиграли!' }
      : { tone: 'muted', text: 'Розыгрыш завершён' }
  } else if (isCancelled) {
    status = { tone: 'muted', text: 'Розыгрыш отменён' }
  } else if (giveaway.joined) {
    status = { tone: 'joined', text: isTimer ? '🎟️ Вы участвуете' : '✅ Приз получен' }
  } else if (isUpcoming) {
    status = { tone: 'upcoming', text: '⏳ Скоро старт' }
  } else if (!conditionsDone) {
    status = { tone: 'locked', text: '🔒 Выполните условия' }
  } else {
    status = { tone: 'ready', swipe: true, text: 'Готово — смахните' }
  }

  const stateClass = isCompleted
    ? ' giveaway-card--completed'
    : giveaway.joined
      ? ' giveaway-card--joined'
      : ''

  const conditionsStat = giveaway.conditionsCount === 0
    ? { val: '—', label: 'без условий', done: false }
    : giveaway.conditionsMet
      ? { val: '✓', label: 'выполнено', done: true }
      : { val: String(giveaway.conditionsCount), label: 'условий', done: false }

  return (
    <button
      type="button"
      data-no-swipe
      className={`giveaway-card giveaway-card--${giveaway.rarity}${stateClass}${swiping ? ' giveaway-card--swiping' : ''}`}
      style={{
        '--r-strong': accent.strong,
        '--r-glow': accent.glow,
        '--r-soft': accent.soft,
        transform: dragX ? `translateX(${dragX}px)` : undefined,
      }}
      onClick={() => { if (!dragX) onOpenDetail(giveaway.id) }}
      onTouchStart={onTouchStart}
      onTouchMove={onTouchMove}
      onTouchEnd={onTouchEnd}
    >
      <div className="giveaway-card-top">
        <span className="giveaway-card-rarity">{RARITY_LABEL[giveaway.rarity] ?? giveaway.rarity}</span>
        <span className="giveaway-card-serial">№ {String(giveaway.id).padStart(4, '0')}</span>
      </div>

      {shownBadges.length > 0 && (
        <div className="giveaway-card-badges">
          {shownBadges.map((b) => (
            <span key={b.key} className={`giveaway-card-badge giveaway-card-badge--${b.mod}`}>{b.text}</span>
          ))}
        </div>
      )}

      <div className="giveaway-card-hero">
        <div className="giveaway-card-icon-wrap">
          <span className="giveaway-card-icon-glow" aria-hidden />
          <span className="giveaway-card-icon-disc" aria-hidden />
          {isLegendary && (
            <>
              <span className="giveaway-card-spark giveaway-card-spark--1" aria-hidden />
              <span className="giveaway-card-spark giveaway-card-spark--2" aria-hidden />
              <span className="giveaway-card-spark giveaway-card-spark--3" aria-hidden />
              <span className="giveaway-card-spark giveaway-card-spark--4" aria-hidden />
            </>
          )}
          <span className="giveaway-card-icon" aria-hidden>{giveaway.emoji}</span>
        </div>
        <span className="giveaway-card-eyebrow">{giveaway.title}</span>
        <span className="giveaway-card-prize">{formatGiveawayPrize(giveaway.prize)}</span>
      </div>

      {countdown && (
        <div className={`giveaway-card-timer${urgent ? ' giveaway-card-timer--urgent' : ''}`}>
          <span className="giveaway-card-timer-label">{isUpcoming ? 'До старта' : 'Осталось'}</span>
          <span className="giveaway-card-timer-value">{countdown}</span>
        </div>
      )}

      <div className="giveaway-card-perf" aria-hidden />

      <div className="giveaway-card-stats">
        <div className="giveaway-card-stat">
          <span className="giveaway-card-stat-val">{isTimer ? '1' : '∞'}</span>
          <span className="giveaway-card-stat-label">🏆 {isTimer ? 'победитель' : 'каждому'}</span>
        </div>
        <div className="giveaway-card-stat">
          <span className="giveaway-card-stat-val">{giveaway.participantsCount ?? 0}</span>
          <span className="giveaway-card-stat-label">👥 участников</span>
        </div>
        <div className={`giveaway-card-stat${conditionsStat.done ? ' giveaway-card-stat--done' : ''}`}>
          <span className="giveaway-card-stat-val">{conditionsStat.val}</span>
          <span className="giveaway-card-stat-label">{conditionsStat.label}</span>
        </div>
      </div>

      <div className={`giveaway-card-status giveaway-card-status--${status.tone}`}>
        {status.text}
        {status.swipe && <span className="giveaway-swipe-arrow" aria-hidden>→</span>}
      </div>
    </button>
  )
}
