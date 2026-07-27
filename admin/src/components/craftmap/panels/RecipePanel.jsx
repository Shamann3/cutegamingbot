function itemLabel(emoji, name, id) {
  return `${emoji || '❓'} ${name || id} #${id}`
}

export default function RecipePanel({ recipe, onClose, canEdit = false, onDelete }) {
  if (!recipe) return null
  const enabled = recipe.enabled !== false

  return (
    <aside className="craftmap-recipe-panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 className="panel-users-subtitle" style={{ margin: 0 }}>
          ⚗ {recipe.displayName || recipe.key}
        </h3>
        <button className="pu-close-btn" onClick={onClose}>✕</button>
      </div>
      <p className="panel-shelf-muted">#{recipe.id} · {recipe.key}</p>

      <h4 className="panel-shelf-label" style={{ marginTop: 14 }}>Ингредиенты</h4>
      <div className="panel-shelf-muted">{itemLabel(recipe.ingredientAEmoji, recipe.ingredientAName, recipe.ingredientAId)}</div>
      <div className="panel-shelf-muted">{itemLabel(recipe.ingredientBEmoji, recipe.ingredientBName, recipe.ingredientBId)}</div>

      <h4 className="panel-shelf-label" style={{ marginTop: 14 }}>Результат</h4>
      <div className="panel-shelf-muted">
        {itemLabel(recipe.resultEmoji, recipe.resultName, recipe.resultItemId)} ×{recipe.resultQty}
      </div>

      <h4 className="panel-shelf-label" style={{ marginTop: 14 }}>Параметры</h4>
      <p className="panel-shelf-muted">Шанс успеха: {recipe.successPercent}%</p>
      <p className="panel-shelf-muted">Состояние: {enabled ? 'включён' : 'выключен'}</p>
      {recipe.remains > 0 ? (
        <p className="panel-shelf-muted">Лимит использований: {recipe.remains}</p>
      ) : null}

      {canEdit ? (
        <button className="panel-users-btn" style={{ marginTop: 16, width: '100%' }}
          onClick={() => onDelete && onDelete(recipe)}>
          🗑 Удалить рецепт
        </button>
      ) : null}
    </aside>
  )
}
