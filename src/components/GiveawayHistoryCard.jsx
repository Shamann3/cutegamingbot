import { RARITY_ACCENT, formatGiveawayPrize } from '../constants/giveaways'

export default function GiveawayHistoryCard({ giveaway }) {
  const accent = RARITY_ACCENT[giveaway.rarity] ?? RARITY_ACCENT.common

  return (
    <div
      className="giveaway-history-card"
      style={{ '--ticket-accent-strong': accent.strong, '--ticket-accent-glow': accent.glow }}
    >
      <span className="giveaway-history-emoji" aria-hidden>{giveaway.emoji}</span>
      <div className="giveaway-history-info">
        <span className="giveaway-history-title">{giveaway.title}</span>
        <span className="giveaway-history-result">
          {giveaway.winnerName
            ? `🏆 Победитель: ${giveaway.winnerName}`
            : `🎁 ${giveaway.recipientsCount ?? 0} игроков получили приз`}
        </span>
      </div>
      <span className="giveaway-history-prize">{formatGiveawayPrize(giveaway.prize)}</span>
    </div>
  )
}
