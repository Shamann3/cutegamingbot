import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ReactFlow, Background, Controls, MiniMap, useNodesState, useEdgesState,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { fetchCraftMap, saveCraftMapPositions } from '../../lib/adminClient'
import { notifyAdmin } from '../../lib/notify'
import { buildGraph } from './graph/buildGraph'
import { layoutGraph } from './graph/layout'
import { traverseChain, detectErrors, computeStats } from './graph/analysis'
import ItemNode from './nodes/ItemNode'
import { useCraftMapState } from './useCraftMapState'
import SearchBar from './panels/SearchBar'
import FilterPanel from './panels/FilterPanel'
import PropertiesPanel from './panels/PropertiesPanel'
import ContextMenu from './panels/ContextMenu'
import StatsBar from './panels/StatsBar'
import ErrorsPanel from './panels/ErrorsPanel'

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
  const mapState = useCraftMapState(graph)
  const [selectedId, setSelectedId] = useState(null)
  const [ctxMenu, setCtxMenu] = useState(null)

  const selectedItem = useMemo(
    () => (selectedId ? (graph.index.itemsById.get(selectedId) || graph.nodes.find((n) => n.id === selectedId)?.item) : null),
    [selectedId, graph],
  )

  useEffect(() => {
    const { matchedIds, visibleIds } = mapState
    const searching = matchedIds.size > 0
    setNodes((prev) => prev.map((n) => {
      const hiddenByFilter = !visibleIds.has(n.id)
      const dimmed = hiddenByFilter || (searching && !matchedIds.has(n.id))
      const highlighted = searching && matchedIds.has(n.id)
      return { ...n, hidden: hiddenByFilter, data: { ...n.data, dimmed, highlighted } }
    }))
  }, [mapState.matchedIds, mapState.visibleIds, setNodes])

  const chain = useMemo(
    () => (selectedId ? traverseChain(selectedId, graph) : null),
    [selectedId, graph],
  )

  const errors = useMemo(() => detectErrors(graph, raw.items), [graph, raw.items])
  const stats = useMemo(() => computeStats(graph, raw.items, errors), [graph, raw.items, errors])

  useEffect(() => {
    if (!chain) return
    setNodes((prev) => prev.map((n) => ({
      ...n,
      data: {
        ...n.data,
        dimmed: !chain.nodes.has(n.id),
        highlighted: n.id === selectedId,
      },
    })))
    setEdges((prev) => prev.map((e) => ({
      ...e,
      animated: chain.edges.has(e.id),
      style: { ...(e.style || {}), opacity: chain.edges.has(e.id) ? 1 : 0.12 },
    })))
  }, [chain, selectedId, setNodes, setEdges])

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

  const onNodeClick = useCallback((_evt, node) => { setSelectedId(node.id) }, [])
  const onPaneClick = useCallback(() => {
    setSelectedId(null)
    setEdges((prev) => prev.map((e) => ({ ...e, animated: false, style: { ...(e.style || {}), opacity: 1 } })))
    setNodes((prev) => prev.map((n) => ({ ...n, data: { ...n.data, dimmed: false, highlighted: false } })))
  }, [setNodes, setEdges])

  const focusItems = useCallback((itemIds) => {
    const set = new Set(itemIds.map(String))
    setNodes((prev) => prev.map((n) => ({
      ...n,
      data: { ...n.data, errored: set.has(n.id), dimmed: set.size > 0 && !set.has(n.id) },
    })))
  }, [setNodes])

  const goTo = useCallback((itemId) => {
    const id = String(itemId)
    setSelectedId(id)
    const node = nodes.find((n) => n.id === id)
    if (node && rfRef.current) {
      // node is ~230x120; offset to its center
      rfRef.current.setCenter(node.position.x + 115, node.position.y + 60, { zoom: 1.2, duration: 400 })
    }
  }, [nodes])

  const onNodeContextMenu = useCallback((evt, node) => {
    evt.preventDefault()
    const item = graph.index.itemsById.get(node.id) || node.data.item
    setCtxMenu({
      x: evt.clientX,
      y: evt.clientY,
      actions: [
        { label: '🔗 Показать цепочку', onClick: () => setSelectedId(node.id) },
        { label: '✨ Выделить связанные', onClick: () => setSelectedId(node.id) },
        { label: '🎯 Центрировать', onClick: () => goTo(node.id) },
        { label: '📋 Копировать ID', onClick: () => navigator.clipboard?.writeText(node.id) },
        { label: '🔗 Копировать ссылку', onClick: () => navigator.clipboard?.writeText(`${window.location.origin}${window.location.pathname}#craft-item-${node.id}`) },
      ],
    })
  }, [graph, goTo])

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
    <>
      <StatsBar stats={stats} />
      <div className="craftmap-wrap">
        <div className="craftmap-toolbar">
          <button className="panel-users-btn" onClick={runAutoLayout} disabled={loading}>⤢ Авто-раскладка</button>
          <button className="panel-users-btn" onClick={load} disabled={loading}>↻ Обновить</button>
          <SearchBar query={mapState.query} onChange={mapState.setQuery} count={mapState.matchedIds.size} />
          <FilterPanel categories={mapState.categories} hidden={mapState.hiddenCategories} onToggle={mapState.toggleCategory} />
          <span className="panel-shelf-muted">{loading ? 'Загрузка…' : `${graph.nodes.length} предметов · ${graph.edges.length} связей`}</span>
        </div>
        <ReactFlow
          className="craftmap-flow"
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeDragStop={onNodeDragStop}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          onNodeContextMenu={onNodeContextMenu}
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
        {selectedItem ? (
          <PropertiesPanel item={selectedItem} graph={graph} onClose={onPaneClick} onGoTo={goTo} />
        ) : null}
        {ctxMenu ? <ContextMenu x={ctxMenu.x} y={ctxMenu.y} actions={ctxMenu.actions} onClose={() => setCtxMenu(null)} /> : null}
        <ErrorsPanel errors={errors} onFocus={focusItems} />
      </div>
    </>
  )
}
