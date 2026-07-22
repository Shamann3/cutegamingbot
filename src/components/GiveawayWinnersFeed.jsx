import { useEffect, useState } from 'react'
import { useGiveawayWinnersFeed } from '../hooks/useGiveawayWinnersFeed'
import { formatGiveawayPrize } from '../constants/giveaways'

const ROTATE_MS = 4000

function timeAgo(iso) {
  const diffMs = Date.now() - new Date(iso).getTime()
  const minutes = Math.max(1, Math.round(diffMs / 60000))
  if (minutes < 60) return `${minutes} мин. назад`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} ч. назад`
  const days = Math.round(hours / 24)
  return `${days} дн. назад`
}

export default function GiveawayWinnersFeed() {
  const { winners } = useGiveawayWinnersFeed()
  const [index, setIndex] = useState(0)

  useEffect(() => {
    if (winners.length < 2) return undefined
    const timer = window.setInterval(() => {
      setIndex((i) => (i + 1) % winners.length)
    }, ROTATE_MS)
    return () => window.clearInterval(timer)
  }, [winners.length])

  if (winners.length === 0) return null

  const current = winners[index % winners.length]

  return (
    <div className="giveaway-winners-feed" key={current.at}>
      <span className="giveaway-winners-feed-medal" aria-hidden>🏆</span>
      <span className="giveaway-winners-feed-text">
        <span className="giveaway-winners-feed-name">{current.displayName}</span>
        {' выиграл '}{formatGiveawayPrize(current.prize)} в «{current.giveawayTitle}»
      </span>
      <span className="giveaway-winners-feed-time">{timeAgo(current.at)}</span>
    </div>
  )
}
