import { RARITY_ACCENT, formatGiveawayPrize } from '../constants/giveaways'
import UserNameLink from './UserNameLink'

export default function GiveawayHistoryCard({ giveaway, onOpenDetail }) {
  const accent = RARITY_ACCENT[giveaway.rarity] ?? RARITY_ACCENT.common

  return (
    <div
      className="giveaway-history-card"
      role="button"
      tabIndex={0}
      style={{ '--ticket-accent-strong': accent.strong, '--ticket-accent-glow': accent.glow }}
      onClick={() => onOpenDetail?.(giveaway.id)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') onOpenDetail?.(giveaway.id)
      }}
    >
      <span className="giveaway-history-medal" aria-hidden>{giveaway.emoji}</span>
      <div className="giveaway-history-info">
        <span className="giveaway-history-title">{giveaway.title}</span>
        <span className="giveaway-history-result">
          {giveaway.winnerName ? (
            <>
              👑{' '}
              <UserNameLink
                userId={giveaway.winnerUserId}
                name={giveaway.winnerName}
                className="giveaway-history-result-winner"
                stopPropagation
              />
            </>
          ) : (
            `🎁 ${giveaway.recipientsCount ?? 0} игроков получили приз`
          )}
        </span>
      </div>
      <span className="giveaway-history-prize">{formatGiveawayPrize(giveaway.prize)}</span>
    </div>
  )
}
