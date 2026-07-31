import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  ReactFlow, Background, Controls, MiniMap, useNodesState, useEdgesState,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { fetchCraftMap, saveCraftMapPositions, deleteContentCraft } from '../../lib/adminClient'
import { notifyAdmin } from '../../lib/notify'
import AdminActionModal from '../AdminActionModal'
import { buildGraph } from './graph/buildGraph'
import { layoutGraph } from './graph/layout'
import { traverseChain, detectErrors, computeStats } from './graph/analysis'
import { nodeVisual, edgeVisual } from './graph/viewState'
import ItemNode from './nodes/ItemNode'
import RecipeNode from './nodes/RecipeNode'
import { useCraftMapState } from './useCraftMapState'
import SearchBar from './panels/SearchBar'
import FilterPanel from './panels/FilterPanel'
import PropertiesPanel from './panels/PropertiesPanel'
import RecipePanel from './panels/RecipePanel'
import ContextMenu from './panels/ContextMenu'
import StatsBar from './panels/StatsBar'
import ErrorsPanel from './panels/ErrorsPanel'
import AddCraftPanel from './panels/AddCraftPanel'

const nodeTypes = { item: ItemNode, recipe: RecipeNode }

function toFlowNodes(graph, positions) {
  return graph.nodes.map((n) => ({
    id: n.id,
    type: n.kind === 'recipe' ? 'recipe' : 'item',
    position: positions[n.id] || { x: 0, y: 0 },
    data: n.kind === 'recipe'
      ? { recipe: n.recipe, dimmed: false, highlighted: false, errored: false }
      : { item: n.item, dimmed: false, highlighted: false, errored: false },
  }))
}

function toFlowEdges(graph) {
  return graph.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    animated: false,
    data: { recipeId: e.recipeId, recipeKey: e.recipeKey, resultQty: e.resultQty, enabled: e.enabled },
    style: e.enabled ? undefined : { strokeDasharray: '5 5', opacity: 0.6 },
  }))
}

export default function CraftMapView({ canEdit = false }) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [raw, setRaw] = useState({ items: [], recipes: [], positions: {} })
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const saveTimer = useRef(null)
  const pendingPositions = useRef(new Map())
  const rfRef = useRef(null)

  const graph = useMemo(() => buildGraph(raw.items, raw.recipes), [raw.items, raw.recipes])
  const mapState = useCraftMapState(graph)
  const [selectedId, setSelectedId] = useState(null)
  const [errorFocus, setErrorFocus] = useState(null) // Set<string> | null
  const [ctxMenu, setCtxMenu] = useState(null)
  const [showAdd, setShowAdd] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null) // recipe object | null
  const [deleting, setDeleting] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)

  useEffect(() => {
    if (!fullscreen) return undefined
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const id = window.requestAnimationFrame(() => {
      window.dispatchEvent(new Event('resize'))
      rfRef.current?.fitView?.({ padding: 0.12, duration: 200 })
    })
    return () => {
      document.body.style.overflow = prevOverflow
      window.cancelAnimationFrame(id)
      window.requestAnimationFrame(() => {
        window.dispatchEvent(new Event('resize'))
        rfRef.current?.fitView?.({ padding: 0.15, duration: 180 })
      })
    }
  }, [fullscreen])

  const selectedNode = useMemo(
    () => (selectedId ? graph.nodes.find((n) => n.id === selectedId) || null : null),
    [selectedId, graph],
  )
  const selectedItem = useMemo(() => {
    if (!selectedNode || selectedNode.kind === 'recipe') return null
    return graph.index.itemsById.get(selectedNode.id) || selectedNode.item
  }, [selectedNode, graph])
  const selectedRecipe = selectedNode && selectedNode.kind === 'recipe' ? selectedNode.recipe : null

  const chain = useMemo(
    () => (selectedId ? traverseChain(selectedId, graph) : null),
    [selectedId, graph],
  )

  const errors = useMemo(() => detectErrors(graph, raw.items), [graph, raw.items])
  const stats = useMemo(() => computeStats(graph, raw.items, errors), [graph, raw.items, errors])

  useEffect(() => {
    const ctx = {
      selectedId,
      chainNodes: chain ? chain.nodes : null,
      chainEdges: chain ? chain.edges : null,
      matchedIds: mapState.matchedIds,
      visibleIds: mapState.visibleIds,
      errorFocus,
    }
    setNodes((prev) => prev.map((n) => {
      const v = nodeVisual(n.id, ctx)
      return { ...n, hidden: v.hidden, data: { ...n.data, dimmed: v.dimmed, highlighted: v.highlighted, errored: v.errored } }
    }))
    setEdges((prev) => prev.map((e) => {
      const v = edgeVisual(e.id, e.data?.enabled !== false, ctx)
      const style = { ...(e.style || {}), opacity: v.opacity }
      if (v.dashed) style.strokeDasharray = '5 5'
      else delete style.strokeDasharray
      return { ...e, animated: v.animated, style }
    }))
  }, [selectedId, chain, mapState.matchedIds, mapState.visibleIds, errorFocus, setNodes, setEdges])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    setErrorFocus(null)
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
    for (const n of changedNodes) {
      pendingPositions.current.set(n.id, { itemId: n.id, x: n.position.x, y: n.position.y })
    }
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(async () => {
      const payload = [...pendingPositions.current.values()]
      pendingPositions.current.clear()
      if (!payload.length) return
      try {
        await saveCraftMapPositions(payload)
      } catch {
        notifyAdmin('Не удалось сохранить позиции', { error: true })
      }
    }, 500)
  }, [])

  const onNodeDragStop = useCallback((_evt, node) => { persist([node]) }, [persist])

  // Every selection path must clear the error focus, otherwise nodeVisual's
  // errorFocus precedence hides the chain highlight the user just asked for.
  const select = useCallback((id) => {
    setErrorFocus(null)
    setSelectedId(String(id))
  }, [])

  const onNodeClick = useCallback((_evt, node) => { select(node.id) }, [select])
  const onPaneClick = useCallback(() => {
    setSelectedId(null)
    setErrorFocus(null)
  }, [])

  const focusItems = useCallback((itemIds) => {
    setSelectedId(null)
    setErrorFocus(new Set(itemIds.map(String)))
  }, [])

  const goTo = useCallback((itemId) => {
    const id = String(itemId)
    select(id)
    const node = nodes.find((n) => n.id === id)
    if (node && rfRef.current) {
      // node is ~230x120; offset to its center
      rfRef.current.setCenter(node.position.x + 115, node.position.y + 60, { zoom: 1.2, duration: 400 })
    }
  }, [nodes, select])

  const onNodeContextMenu = useCallback((evt, node) => {
    evt.preventDefault()
    const isRecipe = node.type === 'recipe'
    const recipe = isRecipe ? node.data?.recipe : null
    setCtxMenu({
      x: evt.clientX,
      y: evt.clientY,
      actions: isRecipe
        ? [
            { label: '🔗 Показать цепочку', onClick: () => select(node.id) },
            { label: '📋 Копировать ключ', onClick: () => navigator.clipboard?.writeText(recipe?.key || '') },
            ...(canEdit && recipe ? [{ label: '🗑 Удалить рецепт', onClick: () => setDeleteTarget(recipe) }] : []),
          ]
        : [
            { label: '🔗 Показать цепочку', onClick: () => select(node.id) },
            { label: '✨ Выделить связанные', onClick: () => select(node.id) },
            { label: '🎯 Центрировать', onClick: () => goTo(node.id) },
            { label: '📋 Копировать ID', onClick: () => navigator.clipboard?.writeText(node.id) },
            { label: '🔗 Копировать ссылку', onClick: () => navigator.clipboard?.writeText(`${window.location.origin}${window.location.pathname}#craft-item-${node.id}`) },
          ],
    })
  }, [graph, goTo, select, canEdit])

  const runAutoLayout = useCallback(() => {
    const positions = layoutGraph(graph.nodes, graph.edges)
    setNodes((prev) => prev.map((n) => ({ ...n, position: positions[n.id] || n.position })))
    const payload = graph.nodes.map((n) => ({ itemId: n.id, x: positions[n.id].x, y: positions[n.id].y }))
    saveCraftMapPositions(payload).catch(() => notifyAdmin('Не удалось сохранить раскладку', { error: true }))
  }, [graph, setNodes])

  const confirmDelete = useCallback(async () => {
    if (!deleteTarget || deleting) return
    setDeleting(true)
    try {
      await deleteContentCraft(deleteTarget.id)
      notifyAdmin('Крафт удалён')
      setDeleteTarget(null)
      setSelectedId(null)
      await load()
    } catch (err) {
      notifyAdmin(err?.message || 'Не удалось удалить крафт', { error: true })
    } finally {
      setDeleting(false)
    }
  }, [deleteTarget, deleting, load])

  if (error) {
    return (
      <div className="craftmap-shell">
        <div className="craftmap-wrap craftmap-wrap-empty">
          <div className="craftmap-empty">
            <p className="panel-shelf-muted">{error}</p>
            <button type="button" className="panel-users-btn panel-users-btn-primary" onClick={load}>Повторить</button>
          </div>
        </div>
      </div>
    )
  }

  const shell = (
    <div
      className={`craftmap-shell${fullscreen ? ' craftmap-shell-fs' : ''}`}
      role={fullscreen ? 'dialog' : undefined}
      aria-modal={fullscreen ? true : undefined}
      aria-label={fullscreen ? 'Карта крафта на весь экран' : undefined}
    >
      {fullscreen ? (
        <div className="craftmap-fs-bar">
          <div className="craftmap-fs-title">
            <span className="craftmap-fs-kicker">Content · Карта</span>
            <strong>Карта крафта</strong>
          </div>
          <button
            type="button"
            className="panel-users-btn"
            data-craftmap-fs-exit
            onClick={() => setFullscreen(false)}
          >
            ✕ Свернуть
          </button>
        </div>
      ) : null}
      <StatsBar stats={stats} />
      <div className="craftmap-toolbar">
        <button type="button" className="panel-users-btn" onClick={runAutoLayout} disabled={loading}>⤢ Авто-раскладка</button>
        <button type="button" className="panel-users-btn" onClick={load} disabled={loading}>↻ Обновить</button>
        {canEdit ? (
          <button type="button" className="panel-users-btn panel-users-btn-primary" onClick={() => setShowAdd(true)}>
            ＋ Новый крафт
          </button>
        ) : null}
        <SearchBar query={mapState.query} onChange={mapState.setQuery} count={mapState.matchedIds.size} />
        <FilterPanel categories={mapState.categories} hidden={mapState.hiddenCategories} onToggle={mapState.toggleCategory} />
        <span className="panel-shelf-muted">
          {loading ? 'Загрузка…' : `${graph.nodes.filter((n) => n.kind === 'item').length} предметов · ${stats.links} связей`}
        </span>
        <button
          type="button"
          className={`panel-users-btn${fullscreen ? '' : ' panel-users-btn-primary'} craftmap-fs-toggle`}
          data-craftmap-fs-exit={fullscreen ? true : undefined}
          onClick={() => setFullscreen((v) => !v)}
          title={fullscreen ? 'Свернуть (Esc)' : 'Открыть на весь экран'}
        >
          {fullscreen ? '⛶ Свернуть' : '⛶ На весь экран'}
        </button>
      </div>
      <div className="craftmap-wrap">
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
        {selectedRecipe ? (
          <RecipePanel recipe={selectedRecipe} onClose={onPaneClick}
            canEdit={canEdit} onDelete={(r) => setDeleteTarget(r)} />
        ) : selectedItem ? (
          <PropertiesPanel item={selectedItem} graph={graph} onClose={onPaneClick} onGoTo={goTo}
            canEdit={canEdit} onDeleteRecipe={(r) => setDeleteTarget(r)} />
        ) : null}
        {ctxMenu ? <ContextMenu x={ctxMenu.x} y={ctxMenu.y} actions={ctxMenu.actions} onClose={() => setCtxMenu(null)} /> : null}
        {showAdd ? <AddCraftPanel onClose={() => setShowAdd(false)} onCreated={() => { setShowAdd(false); load() }} /> : null}
        {deleteTarget ? (
          <AdminActionModal open danger
            title={`Удалить рецепт «${deleteTarget.displayName || deleteTarget.key}»?`}
            description="Рецепт будет удалён из craft_recipes и сразу исчезнет из игры."
            confirmText="Удалить"
            onConfirm={confirmDelete}
            onCancel={() => setDeleteTarget(null)} />
        ) : null}
        <ErrorsPanel errors={errors} onFocus={focusItems} />
      </div>
    </div>
  )

  if (fullscreen && typeof document !== 'undefined') {
    return createPortal(shell, document.body)
  }
  return shell
}
