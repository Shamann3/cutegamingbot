export default function PropertiesPanel({ item, graph, onClose, onGoTo, canEdit = false, onDeleteRecipe }) {
  if (!item) return null
  const { index } = graph
  const producedBy = (index.producedBy.get(item.id) || []).map((rid) => index.recipesById.get(rid)).filter(Boolean)
  const usedIn = (index.usedIn.get(item.id) || []).map((rid) => index.recipesById.get(rid)).filter(Boolean)

  const recipeLine = (r) => `${r.ingredientAEmoji || '❓'} + ${r.ingredientBEmoji || '❓'} → ${r.resultEmoji || '❓'} ×${r.resultQty}`

  return (
    <aside className="craftmap-props">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 className="panel-users-subtitle" style={{ margin: 0 }}>{item.emoji} {item.name}</h3>
        <button className="pu-close-btn" onClick={onClose}>✕</button>
      </div>
      <p className="panel-shelf-muted">#{item.id}{item.sorting ? ` · ${item.sorting}` : ''}</p>
      {item.name1 ? <p className="panel-shelf-muted">{item.name1}</p> : null}
      {typeof item.price === 'number' && item.price > 0 ? <p>💰 {item.price.toLocaleString('ru-RU')} КУТ</p> : null}
      {item.bio ? <p><b>Описание:</b> {item.bio}</p> : null}
      {item.use ? <p><b>Использование:</b> {item.use}</p> : null}
      {item.bonus ? <p><b>Бонус:</b> {item.bonus}</p> : null}

      <h4 className="panel-shelf-label" style={{ marginTop: 14 }}>Рецепты создания ({producedBy.length})</h4>
      {producedBy.length ? producedBy.map((r) => (
        <div key={r.id} className="craftmap-recipe-row">
          <span className="panel-shelf-muted">{recipeLine(r)}</span>
          {canEdit ? (
            <button className="craftmap-recipe-del" title="Удалить рецепт" onClick={() => onDeleteRecipe && onDeleteRecipe(r)}>🗑</button>
          ) : null}
        </div>
      )) : <p className="panel-shelf-muted">— базовый ресурс —</p>}

      <h4 className="panel-shelf-label" style={{ marginTop: 14 }}>Используется в ({usedIn.length})</h4>
      {usedIn.length ? usedIn.map((r) => (
        <button key={r.id} className="panel-users-btn" style={{ display: 'block', width: '100%', textAlign: 'left', marginTop: 4 }}
          onClick={() => onGoTo(r.resultItemId)}>
          → {r.resultEmoji} {r.resultName}
        </button>
      )) : <p className="panel-shelf-muted">— нигде не используется —</p>}
    </aside>
  )
}
