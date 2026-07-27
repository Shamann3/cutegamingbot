import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'

function RecipeNodeBase({ data }) {
  const { recipe, dimmed, highlighted, errored } = data
  const enabled = recipe.enabled !== false
  const cls = [
    'craftmap-recipe-node',
    dimmed ? 'craftmap-node-dim' : '',
    highlighted ? 'craftmap-node-hl' : '',
    errored ? 'craftmap-node-error' : '',
    enabled ? '' : 'craftmap-recipe-node-off',
  ].filter(Boolean).join(' ')

  const title = recipe.displayName || recipe.key || `#${recipe.id}`

  return (
    <div className={cls} title={title}>
      <Handle type="target" position={Position.Left} className="craftmap-handle" />
      <div className="craftmap-recipe-main">
        <span className="craftmap-recipe-icon" aria-hidden>⚗</span>
        <span className="craftmap-recipe-pct">{recipe.successPercent}%</span>
        <span className="craftmap-recipe-qty">×{recipe.resultQty}</span>
      </div>
      <div className="craftmap-recipe-name">{title}</div>
      <Handle type="source" position={Position.Right} className="craftmap-handle" />
    </div>
  )
}

export default memo(RecipeNodeBase)
