export default function FilterPanel({ categories, hidden, onToggle }) {
  if (!categories.length) return null
  return (
    <div className="craftmap-filters" style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
      {categories.map((cat) => (
        <button
          key={cat}
          type="button"
          className={`craftmap-node-tag${hidden.has(cat) ? '' : ' craftmap-tag-active'}`}
          style={{ cursor: 'pointer', opacity: hidden.has(cat) ? 0.4 : 1 }}
          onClick={() => onToggle(cat)}
        >
          {cat}
        </button>
      ))}
    </div>
  )
}
