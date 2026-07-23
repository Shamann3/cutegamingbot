const FIELDS = [
  ['items', 'Предметов'],
  ['recipes', 'Рецептов'],
  ['links', 'Связей'],
  ['baseResources', 'Базовых'],
  ['finalItems', 'Конечных'],
  ['maxDepth', 'Макс. глубина'],
  ['avgDepth', 'Сред. глубина'],
  ['errors', 'Ошибок'],
]

export default function StatsBar({ stats }) {
  if (!stats) return null
  return (
    <div className="craftmap-stats">
      {FIELDS.map(([key, label]) => (
        <div className="craftmap-stat" key={key}>
          <span className="craftmap-stat-value" style={key === 'errors' && stats.errors > 0 ? { color: '#ff6b6b' } : undefined}>
            {stats[key]}
          </span>
          <span className="craftmap-stat-label">{label}</span>
        </div>
      ))}
    </div>
  )
}
