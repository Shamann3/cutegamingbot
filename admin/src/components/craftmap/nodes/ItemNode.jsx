import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'

function ItemNodeBase({ data }) {
  const { item, dimmed, highlighted, errored } = data
  const cls = [
    'craftmap-node',
    dimmed ? 'craftmap-node-dim' : '',
    highlighted ? 'craftmap-node-hl' : '',
    errored ? 'craftmap-node-error' : '',
    item.missing ? 'craftmap-node-missing' : '',
  ].filter(Boolean).join(' ')

  return (
    <div className={cls}>
      <Handle type="target" position={Position.Left} className="craftmap-handle" />
      <div className="craftmap-node-emoji">{item.emoji || '📦'}</div>
      <div className="craftmap-node-body">
        <div className="craftmap-node-name" title={item.name}>{item.name}</div>
        <div className="craftmap-node-meta">
          <span className="craftmap-node-id">#{item.id}</span>
          {item.sorting ? <span className="craftmap-node-tag">{item.sorting}</span> : null}
        </div>
        {typeof item.price === 'number' && item.price > 0 ? (
          <div className="craftmap-node-price">💰 {item.price.toLocaleString('ru-RU')}</div>
        ) : null}
      </div>
      <Handle type="source" position={Position.Right} className="craftmap-handle" />
    </div>
  )
}

export default memo(ItemNodeBase)
