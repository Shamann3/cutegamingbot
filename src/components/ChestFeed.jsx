import { RARITY_ACCENT, RARITY_LABEL } from '../constants/chests'
import UserNameLink from './UserNameLink'

export default function ChestFeed({ feed }) {
  if (!feed || feed.length === 0) return null
  return (
    <div className="chest-feed">
      <div className="chest-feed-head">🔥 Только что выбили</div>
      {feed.slice(0, 6).map((row, i) => (
        <div
          key={row.userId ? `${row.userId}-${row.openedAt || i}` : i}
          className="chest-feed-row"
          style={{ borderLeftColor: RARITY_ACCENT[row.rarity] }}
        >
          <span className="chest-feed-emoji">{row.emoji}</span>
          <span className="chest-feed-text">
            <UserNameLink userId={row.userId} name={row.name} />
            {' выбил '}
            <b>{row.itemName}</b>
          </span>
          <span className="chest-feed-tag" style={{ color: RARITY_ACCENT[row.rarity] }}>
            {RARITY_LABEL[row.rarity]}
          </span>
        </div>
      ))}
    </div>
  )
}
