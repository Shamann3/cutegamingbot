import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ReactFlow, Background, Controls, MiniMap, useNodesState, useEdgesState,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { fetchCraftMap, saveCraftMapPositions } from '../../lib/adminClient'
import { notifyAdmin } from '../../lib/notify'
import { buildGraph } from './graph/buildGraph'
import { layoutGraph } from './graph/layout'
import ItemNode from './nodes/ItemNode'

const nodeTypes = { item: ItemNode }

function toFlowNodes(graph, positions) {
  return graph.nodes.map((n) => ({
    id: n.id,
    type: 'item',
    position: positions[n.id] || { x: 0, y: 0 },
    data: { item: n.item, dimmed: false, highlighted: false, errored: false },
  }))
}

function toFlowEdges(graph) {
  return graph.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    animated: false,
    data: { recipeId: e.recipeId, recipeKey: e.recipeKey, resultQty: e.resultQty },
    style: e.enabled ? undefined : { strokeDasharray: '5 5', opacity: 0.6 },
  }))
}

export default function CraftMapView() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [raw, setRaw] = useState({ items: [], recipes: [], positions: {} })
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const saveTimer = useRef(null)
  const rfRef = useRef(null)

  const graph = useMemo(() => buildGraph(raw.items, raw.recipes), [raw.items, raw.recipes])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchCraftMap()
      const g = buildGraph(data.items, data.recipes)
      const saved = data.positions || {}
      const needLayout = g.nodes.some((n) => !saved[n.id])
      const positions = needLayout
        ? { ...layoutGraph(g.nodes, g.edges), ...saved }
        : saved
      setRaw({ items: data.items, recipes: data.recipes, positions })
      setNodes(toFlowNodes(g, positions))
      setEdges(toFlowEdges(g))
    } catch (err) {
      setError(err?.message || 'Не удалось загрузить карту')
    } finally {
      setLoading(false)
    }
  }, [setNodes, setEdges])

  useEffect(() => { load() }, [load])

  const persist = useCallback((changedNodes) => {
    const payload = changedNodes.map((n) => ({ itemId: n.id, x: n.position.x, y: n.position.y }))
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(async () => {
      try {
        await saveCraftMapPositions(payload)
      } catch {
        notifyAdmin('Не удалось сохранить позиции', { error: true })
      }
    }, 500)
  }, [])

  const onNodeDragStop = useCallback((_evt, node) => { persist([node]) }, [persist])

  const runAutoLayout = useCallback(() => {
    const positions = layoutGraph(graph.nodes, graph.edges)
    setNodes((prev) => prev.map((n) => ({ ...n, position: positions[n.id] || n.position })))
    const payload = graph.nodes.map((n) => ({ itemId: n.id, x: positions[n.id].x, y: positions[n.id].y }))
    saveCraftMapPositions(payload).catch(() => notifyAdmin('Не удалось сохранить раскладку', { error: true }))
  }, [graph, setNodes])

  if (error) {
    return (
      <div className="craftmap-wrap" style={{ display: 'grid', placeItems: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <p className="panel-shelf-muted">{error}</p>
          <button className="panel-users-btn panel-users-btn-primary" onClick={load}>Повторить</button>
        </div>
      </div>
    )
  }

  return (
    <div className="craftmap-wrap">
      <div className="craftmap-toolbar">
        <button className="panel-users-btn" onClick={runAutoLayout} disabled={loading}>⤢ Авто-раскладка</button>
        <button className="panel-users-btn" onClick={load} disabled={loading}>↻ Обновить</button>
        <span className="panel-shelf-muted">{loading ? 'Загрузка…' : `${graph.nodes.length} предметов · ${graph.edges.length} связей`}</span>
      </div>
      <ReactFlow
        className="craftmap-flow"
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeDragStop={onNodeDragStop}
        nodeTypes={nodeTypes}
        onInit={(inst) => { rfRef.current = inst }}
        onlyRenderVisibleElements
        minZoom={0.1}
        maxZoom={2.5}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={22} />
        <MiniMap pannable zoomable />
        <Controls />
      </ReactFlow>
    </div>
  )
}
