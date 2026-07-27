const ICON = { error: '⛔', warning: '⚠️', info: 'ℹ️' }

export default function ErrorsPanel({ errors, onFocus }) {
  if (!errors || !errors.length) return null
  return (
    <div className="craftmap-errors">
      <h4 className="panel-shelf-label" style={{ marginTop: 0 }}>Проверка ({errors.length})</h4>
      {errors.map((e, i) => (
        <button key={`${e.type}-${i}`} type="button" className="panel-users-btn"
          style={{ display: 'block', width: '100%', textAlign: 'left', marginBottom: 4 }}
          onClick={() => onFocus(e.itemIds)}>
          {ICON[e.severity] || '•'} {e.message}
        </button>
      ))}
    </div>
  )
}
