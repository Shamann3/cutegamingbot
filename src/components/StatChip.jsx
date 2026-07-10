import { VineLeaf } from './decor/LeafDecor'

export default function StatChip({ icon, label, value, kind = 'default', muted = false, compact = false }) {
  if (compact) {
    return (
      <div
        className={`farm-stat-chip-compact farm-stat-chip-compact-${kind}`}
        role="listitem"
      >
        <span className="farm-stat-chip-icon" aria-hidden>{icon}</span>
        <div className="farm-stat-chip-text">
          <span className="farm-stat-chip-label">{label}</span>
          <span className="farm-stat-chip-value">{value}</span>
        </div>
      </div>
    )
  }

  return (
    <div
      className={`farm-stat-bar farm-stat-bar-${kind}${muted ? ' farm-stat-bar-muted' : ''}`}
      role="listitem"
    >
      <span className="farm-stat-bar-leaf farm-stat-bar-leaf-l" aria-hidden>
        <VineLeaf className="w-5 h-3" />
      </span>
      <span className="farm-stat-bar-leaf farm-stat-bar-leaf-r" aria-hidden>
        <VineLeaf className="w-5 h-3" flip />
      </span>
      <div className="farm-stat-bar-inner">
        <span className="farm-stat-bar-icon" aria-hidden>{icon}</span>
        <div className="min-w-0">
          <p className="farm-stat-bar-label">{label}</p>
          <p className="farm-stat-bar-value">{value}</p>
        </div>
      </div>
    </div>
  )
}
