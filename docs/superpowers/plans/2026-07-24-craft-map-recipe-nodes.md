# Craft Map — Recipe Nodes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two anonymous `ingredient → result` lines per recipe with an explicit recipe node (`ingredients → [⚗ 80% ×5] → result`), so it is unambiguous which ingredient pair forms which recipe, and show recipe text as `name #id` instead of bare emoji.

**Architecture:** Only the *visual* topology changes. `buildGraph` gains recipe nodes (`r:<id>`) and emits 3 edges per recipe; the semantic indexes (`forward`, `backward`, `producedBy`, `usedIn`) stay item↔item so all analysis (cycles, depth, base/final, unreachable) keeps its current meaning. Consumers are made tolerant of the new node kind BEFORE the model flips, so every task leaves a working app.

**Tech Stack:** React 18, `@xyflow/react`, `@dagrejs/dagre`, vitest. No new dependencies, no backend or schema change.

## Global Constraints

- No backend/schema change. Recipe node positions reuse `craft_map_positions` with keys `r:<recipeId>` (`item_id` is `TEXT`, and the API caps it at 64 chars).
- Pure modules (`buildGraph.js`, `analysis.js`, `viewState.js`) MUST stay free of npm imports so their colocated tests run under repo-root `npm test`.
- **`analysis.errors.test.js` must keep passing WITHOUT modification.** It is the acceptance proof that the semantic layer was not disturbed. If it fails, the indexes drifted — fix the indexes, never the test.
- Semantic indexes (`forward`, `backward`, `producedBy`, `usedIn`) remain item↔item. Recipe nodes exist only in `nodes`/`edges`.
- Stats `links` must keep counting ingredient→result relations (2 per recipe = 30 on live data), NOT the 45 visual edges.
- The craft model is unchanged: exactly 2 ingredients qty 1, one result with `result_qty`.
- Russian UI copy. Editing controls remain gated by the existing `canEdit`.

## Data shapes after this change

```
node (item)   : { id: '<dexId>',  kind: 'item',   item }
node (recipe) : { id: 'r:<rid>',  kind: 'recipe', recipe }

edges (3 per recipe):
  { id: '<rid>:a',   source: ingredientAId, target: 'r:<rid>', slot: 'a'   }
  { id: '<rid>:b',   source: ingredientBId, target: 'r:<rid>', slot: 'b'   }
  { id: '<rid>:out', source: 'r:<rid>',     target: resultItemId, slot: 'out' }
each edge also carries: recipeId, recipeKey, successPercent, resultQty, enabled
```

---

## Task 1: Prep — RecipeNode component, kind-aware rendering, crash guards, layout sizes

This task makes every consumer tolerant of a `kind: 'recipe'` node *before* the model emits any. The app must behave exactly as today after this task (no recipe nodes exist yet).

**Files:**
- Create: `admin/src/components/craftmap/nodes/RecipeNode.jsx`
- Modify: `admin/src/components/craftmap/CraftMapView.jsx` (`toFlowNodes`, `nodeTypes`)
- Modify: `admin/src/components/craftmap/useCraftMapState.js` (guard `n.item`)
- Modify: `admin/src/components/craftmap/graph/layout.js` (per-kind node size)
- Modify: `admin/src/index.css` (append `.craftmap-recipe-node` styles)

**Interfaces:**
- Produces: `RecipeNode` — React Flow custom node registered as type `recipe`, consuming `data = { recipe, dimmed, highlighted, errored }`.
- Produces: `layoutGraph(nodes, edges, opts)` sizes nodes by `node.kind`.

- [ ] **Step 1: Create `RecipeNode.jsx`**

```jsx
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
```

- [ ] **Step 2: Append styles to `admin/src/index.css`**

```css
/* Recipe node — the "machine" between ingredients and result */
.craftmap-recipe-node { display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 2px; width: 120px; padding: 8px 10px; border-radius: 12px;
  background: rgba(46,38,64,.94); border: 1px solid rgba(168,140,255,.35);
  box-shadow: 0 6px 18px rgba(0,0,0,.35);
  transition: transform .15s ease, box-shadow .15s ease, opacity .2s ease, border-color .2s ease; }
.craftmap-recipe-node:hover { transform: translateY(-2px); border-color: rgba(168,140,255,.75); }
.craftmap-recipe-main { display: flex; align-items: baseline; gap: 6px; }
.craftmap-recipe-icon { font-size: 15px; }
.craftmap-recipe-pct { font-size: 12px; font-weight: 600; color: #cdbcff; }
.craftmap-recipe-qty { font-size: 12px; font-weight: 700; color: #eef1f6; }
.craftmap-recipe-name { font-size: 10px; color: #9aa3b8; max-width: 104px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.craftmap-recipe-node-off { border-style: dashed; opacity: .6; }

[data-theme="light"] .craftmap-recipe-node { background: #f6f2ff; border-color: rgba(120,80,220,.35); }
[data-theme="light"] .craftmap-recipe-qty { color: #241a3a; }
[data-theme="light"] .craftmap-recipe-name { color: #6b7280; }
```

- [ ] **Step 3: Make `CraftMapView` rendering kind-aware**

In `admin/src/components/craftmap/CraftMapView.jsx`:

Add the import next to `ItemNode`:
```jsx
import RecipeNode from './nodes/RecipeNode'
```
Change the node type registry:
```jsx
const nodeTypes = { item: ItemNode, recipe: RecipeNode }
```
Replace `toFlowNodes` so it builds data per kind (recipe nodes have `recipe`, not `item`):
```jsx
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
```

- [ ] **Step 4: Guard `useCraftMapState` against nodes without `item`**

In `admin/src/components/craftmap/useCraftMapState.js`, three unguarded `n.item` accesses would throw once recipe nodes exist. Change:

`categories`:
```jsx
    for (const n of graph.nodes) if (n.item && n.item.sorting) set.add(n.item.sorting)
```
`matchedIds` — add a skip at the top of the loop body:
```jsx
    for (const n of graph.nodes) {
      if (!n.item) continue
      const i = n.item
      const hay = [i.id, i.name, i.name1, i.sorting, i.bio].filter(Boolean).join(' ').toLowerCase()
      if (hay.includes(q)) out.add(n.id)
    }
```
`visibleIds`:
```jsx
    for (const n of graph.nodes) {
      if (n.item && n.item.sorting && hiddenCategories.has(n.item.sorting)) continue
      out.add(n.id)
    }
```

- [ ] **Step 5: Size nodes per kind in `layout.js`**

Replace the body of `layoutGraph` in `admin/src/components/craftmap/graph/layout.js`:

```javascript
import Dagre from '@dagrejs/dagre'

// Assigns positions left-to-right: base resources on the left, final items on the right.
export function layoutGraph(nodes, edges, opts = {}) {
  const {
    nodeWidth = 230, nodeHeight = 120,
    recipeWidth = 120, recipeHeight = 64,
    rankdir = 'LR', nodesep = 44, ranksep = 90,
  } = opts
  const sizeOf = (node) => (node.kind === 'recipe'
    ? { width: recipeWidth, height: recipeHeight }
    : { width: nodeWidth, height: nodeHeight })

  const g = new Dagre.graphlib.Graph()
  g.setGraph({ rankdir, nodesep, ranksep })
  g.setDefaultEdgeLabel(() => ({}))

  for (const node of nodes) g.setNode(node.id, sizeOf(node))
  for (const edge of edges) {
    if (g.hasNode(edge.source) && g.hasNode(edge.target)) g.setEdge(edge.source, edge.target)
  }

  Dagre.layout(g)

  const positions = {}
  for (const node of nodes) {
    const p = g.node(node.id)
    const { width, height } = sizeOf(node)
    positions[node.id] = { x: p.x - width / 2, y: p.y - height / 2 }
  }
  return positions
}
```

- [ ] **Step 6: Verify nothing changed behaviourally**

Run: `npm test` — expect all current tests to pass unchanged (no recipe nodes exist yet, so `sizeOf` always returns the item size and the guards are no-ops).
Run: `npm --prefix admin run build` — expect success.

- [ ] **Step 7: Commit**

```bash
git add admin/src/components/craftmap/nodes/RecipeNode.jsx admin/src/components/craftmap/CraftMapView.jsx admin/src/components/craftmap/useCraftMapState.js admin/src/components/craftmap/graph/layout.js admin/src/index.css
git commit -m "feat(craft-map): recipe node component and kind-aware rendering (no model change yet)"
```

---

## Task 2: `buildGraph` — emit recipe nodes and 3 edges per recipe (TDD)

**Files:**
- Modify: `admin/src/components/craftmap/graph/buildGraph.js`
- Modify: `admin/src/components/craftmap/graph/buildGraph.test.js`

**Interfaces:**
- Produces: the node/edge shapes in "Data shapes after this change". Semantic indexes unchanged.

- [ ] **Step 1: Update the tests first (RED)**

Replace the whole body of `admin/src/components/craftmap/graph/buildGraph.test.js` with:

```javascript
import { describe, it, expect } from 'vitest'
import { buildGraph } from './buildGraph.js'

const items = [
  { id: '1', name: 'Бревно', emoji: '🪵', sorting: 'ресурсы' },
  { id: '2', name: 'Вода', emoji: '💧', sorting: 'ресурсы' },
  { id: '3', name: 'Бумага', emoji: '📄', sorting: 'крафт' },
  { id: '9', name: 'Одиночка', emoji: '🧍', sorting: 'прочее' },
]
const recipes = [
  {
    id: 10, key: 'paper', displayName: 'Бумага',
    resultItemId: '3', ingredientAId: '1', ingredientBId: '2',
    successPercent: 100, enabled: true, remains: 0, resultQty: 2,
  },
]

const itemIds = (g) => g.nodes.filter((n) => n.kind === 'item').map((n) => n.id).sort()

describe('buildGraph', () => {
  it('creates an item node per referenced item and skips orphans by default', () => {
    expect(itemIds(buildGraph(items, recipes))).toEqual(['1', '2', '3'])
  })

  it('includes orphan items when includeOrphans is true', () => {
    expect(itemIds(buildGraph(items, recipes, { includeOrphans: true }))).toEqual(['1', '2', '3', '9'])
  })

  it('creates one recipe node per recipe, keyed r:<id>', () => {
    const g = buildGraph(items, recipes)
    const recipeNodes = g.nodes.filter((n) => n.kind === 'recipe')
    expect(recipeNodes).toHaveLength(1)
    expect(recipeNodes[0].id).toBe('r:10')
    expect(recipeNodes[0].recipe.key).toBe('paper')
  })

  it('routes both ingredients into the recipe node and the recipe node to the result', () => {
    const g = buildGraph(items, recipes)
    const byId = Object.fromEntries(g.edges.map((e) => [e.id, e]))
    expect(g.edges).toHaveLength(3)
    expect(byId['10:a']).toMatchObject({ source: '1', target: 'r:10', slot: 'a' })
    expect(byId['10:b']).toMatchObject({ source: '2', target: 'r:10', slot: 'b' })
    expect(byId['10:out']).toMatchObject({ source: 'r:10', target: '3', slot: 'out', resultQty: 2, enabled: true })
  })

  it('keeps the semantic indexes item-to-item (no recipe ids inside)', () => {
    const g = buildGraph(items, recipes)
    expect(g.index.producedBy.get('3')).toEqual([10])
    expect(g.index.usedIn.get('1')).toEqual([10])
    expect([...g.index.forward.get('1')]).toEqual(['3'])
    expect([...g.index.backward.get('3')].sort()).toEqual(['1', '2'])
    expect(g.index.forward.has('r:10')).toBe(false)
    expect(g.index.backward.has('r:10')).toBe(false)
  })

  it('creates placeholder item nodes marked missing for undefined referenced items', () => {
    const g = buildGraph([{ id: '3', name: 'Бумага', emoji: '📄' }], recipes)
    const one = g.nodes.find((n) => n.id === '1')
    expect(one).toBeDefined()
    expect(one.kind).toBe('item')
    expect(one.item.missing).toBe(true)
  })

  it('does not duplicate a recipe id in usedIn when both ingredient slots are the same item', () => {
    const sameItems = [
      { id: '1', name: 'Бревно', emoji: '🪵' },
      { id: '2', name: 'Доска', emoji: '🪵' },
    ]
    const sameRecipes = [
      { id: 20, key: 'plank', resultItemId: '2', ingredientAId: '1', ingredientBId: '1', successPercent: 100, enabled: true, remains: 0, resultQty: 1 },
    ]
    const g = buildGraph(sameItems, sameRecipes)
    expect(g.index.usedIn.get('1')).toEqual([20])
    expect(g.edges.map((e) => e.id).sort()).toEqual(['20:a', '20:b', '20:out'])
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm test -- buildGraph`
Expected: FAIL — nodes have no `kind`, edges target the result directly, `10:out` missing.

- [ ] **Step 3: Implement the new topology**

Replace the `buildGraph` function body in `admin/src/components/craftmap/graph/buildGraph.js` (keep the `pushMap` / `pushMapUnique` / `addSet` helpers as they are):

```javascript
export function buildGraph(items, recipes, { includeOrphans = false } = {}) {
  const itemsById = new Map()
  for (const item of items || []) itemsById.set(String(item.id), item)

  const recipesById = new Map()
  const producedBy = new Map()
  const usedIn = new Map()
  const forward = new Map()
  const backward = new Map()
  const referenced = new Set()
  const edges = []
  const recipeNodes = []

  const ensureItem = (id) => {
    const key = String(id)
    if (itemsById.has(key)) return itemsById.get(key)
    return { id: key, name: key, emoji: '❓', sorting: null, missing: true }
  }

  for (const recipe of recipes || []) {
    const rid = recipe.id
    recipesById.set(rid, recipe)
    const recipeNodeId = `r:${rid}`
    const result = String(recipe.resultItemId)
    const enabled = recipe.enabled !== false
    const meta = {
      recipeId: rid,
      recipeKey: recipe.key,
      successPercent: recipe.successPercent,
      resultQty: recipe.resultQty,
      enabled,
    }
    const slots = [
      ['a', String(recipe.ingredientAId)],
      ['b', String(recipe.ingredientBId)],
    ]

    referenced.add(result)
    for (const [slot, ing] of slots) {
      referenced.add(ing)
      // Visual: ingredient -> recipe node.
      edges.push({ id: `${rid}:${slot}`, source: ing, target: recipeNodeId, slot, ...meta })
      // Semantic: item -> item, so analysis keeps its current meaning.
      pushMapUnique(usedIn, ing, rid)
      addSet(forward, ing, result)
      addSet(backward, result, ing)
    }
    edges.push({ id: `${rid}:out`, source: recipeNodeId, target: result, slot: 'out', ...meta })
    pushMap(producedBy, result, rid)
    recipeNodes.push({ id: recipeNodeId, kind: 'recipe', recipe })
  }

  const nodeIds = includeOrphans
    ? new Set([...itemsById.keys(), ...referenced])
    : referenced

  const itemNodes = [...nodeIds].map((id) => ({ id, kind: 'item', item: ensureItem(id) }))

  return {
    nodes: [...itemNodes, ...recipeNodes],
    edges,
    index: { itemsById, recipesById, producedBy, usedIn, forward, backward },
  }
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `npm test -- buildGraph`
Expected: PASS (7 tests).

- [ ] **Step 5: Confirm the semantic layer is untouched**

Run: `npm test -- analysis.errors`
Expected: PASS **without editing that file**. If it fails, the indexes drifted — fix `buildGraph`, not the test.

- [ ] **Step 6: Build**

Run: `npm --prefix admin run build`
Expected: success.

- [ ] **Step 7: Commit**

```bash
git add admin/src/components/craftmap/graph/buildGraph.js admin/src/components/craftmap/graph/buildGraph.test.js
git commit -m "feat(craft-map): model recipes as graph nodes (3 edges per recipe)"
```

---

## Task 3: `analysis` — semantic link count and cycle edge ids

**Files:**
- Modify: `admin/src/components/craftmap/graph/analysis.js`
- Modify: `admin/src/components/craftmap/graph/analysis.traversal.test.js`

**Interfaces:**
- `computeStats(...).links` counts ingredient→result relations (2 per recipe), not visual edges.
- The `cycle` error's `edgeIds` again covers the edges of the cycle, now routed through recipe nodes.
- `traverseChain` is unchanged in code; its results now include recipe nodes.

- [ ] **Step 1: Update the traversal tests (RED)**

In `admin/src/components/craftmap/graph/analysis.traversal.test.js`, the fixture stays the same (`1+2 → 3`, `3+4 → 5`) but the chain now passes through recipe nodes. Replace the three test bodies with:

```javascript
describe('traverseChain', () => {
  it('collects full upstream (ancestors) of a mid-chain item, including recipe nodes', () => {
    const g = buildGraph(items, recipes)
    const chain = traverseChain('5', g)
    expect([...chain.upstream].sort()).toEqual(['1', '2', '3', '4', 'r:10', 'r:11'])
    expect([...chain.downstream]).toEqual([])
  })

  it('collects full downstream (descendants) of a base resource, including recipe nodes', () => {
    const g = buildGraph(items, recipes)
    const chain = traverseChain('1', g)
    expect([...chain.downstream].sort()).toEqual(['3', '5', 'r:10', 'r:11'])
    expect([...chain.upstream]).toEqual([])
  })

  it('includes the selected node and the connecting edges through the recipe node', () => {
    const g = buildGraph(items, recipes)
    const chain = traverseChain('3', g)
    expect(chain.nodes.has('3')).toBe(true)
    expect(chain.nodes.has('r:10')).toBe(true)
    // upstream: both ingredients into recipe 10, then recipe 10 out to item 3
    expect(chain.edges.has('10:a')).toBe(true)
    expect(chain.edges.has('10:b')).toBe(true)
    expect(chain.edges.has('10:out')).toBe(true)
    // downstream: item 3 feeds recipe 11
    expect(chain.edges.has('11:a')).toBe(true)
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm test -- analysis.traversal`
Expected: FAIL — current expectations lack the `r:` nodes and `:out` edges.

- [ ] **Step 3: Verify traverseChain needs no code change**

`traverseChain` walks `graph.edges` generically, so it already threads through recipe nodes. Do NOT modify it. Re-run:

Run: `npm test -- analysis.traversal`
Expected: PASS (3 tests) with no change to `analysis.js`. If it still fails, the failure is in the expectations — re-derive them by hand from the fixture before touching code.

- [ ] **Step 4: Make the link count semantic**

In `admin/src/components/craftmap/graph/analysis.js`, inside `computeStats`, change the returned `links` from the visual edge count to the ingredient→result relation count:

```javascript
    links: index.recipesById.size * 2,
```
(2 ingredient links per recipe — this reproduces the previous value exactly.)

- [ ] **Step 5: Restore the cycle error's edge ids**

Still in `analysis.js`, inside `detectErrors`, the cycle block filters edges whose *both* endpoints are cycle members. With recipe nodes in between, no edge has both endpoints in `cycleNodes` (which holds only item ids), so `edgeIds` would come back empty. Replace the cycle block with a version that also treats the recipe nodes bridging two cycle members as part of the cycle:

```javascript
  // cycles
  const { found, cycleNodes } = hasCycle(index, nodeIds)
  if (found) {
    // Recipe nodes bridge two item nodes, so a cycle's edges only line up once
    // the bridging recipe nodes are counted as cycle members too.
    const cycleMembers = new Set(cycleNodes)
    for (const recipe of index.recipesById.values()) {
      const result = String(recipe.resultItemId)
      const ings = [String(recipe.ingredientAId), String(recipe.ingredientBId)]
      if (cycleNodes.has(result) && ings.some((i) => cycleNodes.has(i))) {
        cycleMembers.add(`r:${recipe.id}`)
      }
    }
    errors.push({
      type: 'cycle',
      severity: 'error',
      itemIds: [...cycleNodes],
      edgeIds: edges.filter((e) => cycleMembers.has(e.source) && cycleMembers.has(e.target)).map((e) => e.id),
      message: 'Обнаружена циклическая зависимость в рецептах',
    })
  }
```
`itemIds` still holds only real item ids, so the errors panel keeps focusing items.

- [ ] **Step 6: Confirm the semantic tests still pass unmodified**

Run: `npm test -- analysis.errors`
Expected: PASS **without editing that file** — including the `links` assertion (`2 recipes × 2 = 4`) and the cycle-member test.

- [ ] **Step 7: Full suite + build**

Run: `npm test` (all pass) and `npm --prefix admin run build` (success).

- [ ] **Step 8: Commit**

```bash
git add admin/src/components/craftmap/graph/analysis.js admin/src/components/craftmap/graph/analysis.traversal.test.js
git commit -m "feat(craft-map): semantic link count and cycle edges across recipe nodes"
```

---

## Task 4: Selecting a recipe — RecipePanel, selection wiring, context menu

**Files:**
- Create: `admin/src/components/craftmap/panels/RecipePanel.jsx`
- Modify: `admin/src/components/craftmap/CraftMapView.jsx`
- Modify: `admin/src/index.css` (append `.craftmap-recipe-panel` styles)

**Interfaces:**
- Produces: `RecipePanel({ recipe, onClose, canEdit, onDelete })`.
- `CraftMapView` resolves the selected node's kind and renders either `PropertiesPanel` (item) or `RecipePanel` (recipe).

- [ ] **Step 1: Create `RecipePanel.jsx`**

```jsx
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
```

- [ ] **Step 2: Append `.craftmap-recipe-panel` styles to `admin/src/index.css`**

```css
.craftmap-recipe-panel { position: absolute; top: 0; right: 0; height: 100%; width: 320px; z-index: 7;
  background: rgba(16,19,26,.97); border-left: 1px solid rgba(255,255,255,.08);
  box-shadow: -12px 0 30px rgba(0,0,0,.4); overflow-y: auto; padding: 16px; }
[data-theme="light"] .craftmap-recipe-panel { background: #ffffff; color: #1a2230; }
```

- [ ] **Step 3: Resolve selection by kind in `CraftMapView.jsx`**

Add the import with the other panels:
```jsx
import RecipePanel from './panels/RecipePanel'
```

Replace the existing `selectedItem` memo with a kind-aware pair:
```jsx
  const selectedNode = useMemo(
    () => (selectedId ? graph.nodes.find((n) => n.id === selectedId) || null : null),
    [selectedId, graph],
  )
  const selectedItem = useMemo(() => {
    if (!selectedNode || selectedNode.kind === 'recipe') return null
    return graph.index.itemsById.get(selectedNode.id) || selectedNode.item
  }, [selectedNode, graph])
  const selectedRecipe = selectedNode && selectedNode.kind === 'recipe' ? selectedNode.recipe : null
```

Replace the `PropertiesPanel` render block with one that picks the right panel:
```jsx
        {selectedRecipe ? (
          <RecipePanel recipe={selectedRecipe} onClose={onPaneClick}
            canEdit={canEdit} onDelete={(r) => setDeleteTarget(r)} />
        ) : selectedItem ? (
          <PropertiesPanel item={selectedItem} graph={graph} onClose={onPaneClick} onGoTo={goTo}
            canEdit={canEdit} onDeleteRecipe={(r) => setDeleteTarget(r)} />
        ) : null}
```

- [ ] **Step 4: Give recipe nodes their own context menu**

In `onNodeContextMenu`, branch on the node type so a recipe node gets recipe actions. Replace the `setCtxMenu({...})` call with:
```jsx
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
```
Add `canEdit` to the `useCallback` dependency array of `onNodeContextMenu` (it becomes `[graph, goTo, select, canEdit]`).

- [ ] **Step 5: Build**

Run: `npm --prefix admin run build`
Expected: success.

- [ ] **Step 6: Commit**

```bash
git add admin/src/components/craftmap/panels/RecipePanel.jsx admin/src/components/craftmap/CraftMapView.jsx admin/src/index.css
git commit -m "feat(craft-map): recipe details panel and recipe context menu"
```

---

## Task 5: Filter/search edge cases + names instead of emoji

**Files:**
- Modify: `admin/src/components/craftmap/useCraftMapState.js`
- Modify: `admin/src/components/craftmap/panels/PropertiesPanel.jsx`

**Interfaces:**
- A recipe node is *matched* when its result item is matched.
- A recipe node is *hidden* when any of its three linked items is hidden by the category filter.
- Recipe lines read `🌳 Дерево #290 + 🪓 Пила #301 → 🪵 Древесина ×5`.

- [ ] **Step 1: Recipe nodes follow their result in search**

In `useCraftMapState.js`, at the end of the `matchedIds` memo (after the item loop, before `return out`):
```jsx
    // A recipe node counts as matched when its result item matched, so a search
    // doesn't dim the very recipe that produces the highlighted item.
    for (const n of graph.nodes) {
      if (n.kind !== 'recipe' || !n.recipe) continue
      if (out.has(String(n.recipe.resultItemId))) out.add(n.id)
    }
```

- [ ] **Step 2: Recipe nodes hide with their items**

At the end of the `visibleIds` memo (after the item loop, before `return out`):
```jsx
    // A recipe node without its ingredients/result on screen is a dangling
    // orphan — hide it whenever any linked item is filtered out.
    for (const n of graph.nodes) {
      if (n.kind !== 'recipe' || !n.recipe) continue
      const r = n.recipe
      const linked = [String(r.ingredientAId), String(r.ingredientBId), String(r.resultItemId)]
      if (linked.some((id) => !out.has(id))) out.delete(n.id)
    }
```

- [ ] **Step 3: Show names and ids instead of bare emoji**

In `admin/src/components/craftmap/panels/PropertiesPanel.jsx`, replace the `recipeLine` helper:
```jsx
  const itemLabel = (emoji, name, id) => `${emoji || '❓'} ${name || id} #${id}`
  const recipeLine = (r) =>
    `${itemLabel(r.ingredientAEmoji, r.ingredientAName, r.ingredientAId)}`
    + ` + ${itemLabel(r.ingredientBEmoji, r.ingredientBName, r.ingredientBId)}`
    + ` → ${itemLabel(r.resultEmoji, r.resultName, r.resultItemId)} ×${r.resultQty}`
```
These lines are much longer than the old emoji-only ones, so they must wrap inside the narrow panel instead of overflowing. In the same file, change the recipe row's text span to allow wrapping:
```jsx
          <span className="panel-shelf-muted" style={{ minWidth: 0, wordBreak: 'break-word' }}>{recipeLine(r)}</span>
```

- [ ] **Step 4: Build**

Run: `npm --prefix admin run build`
Expected: success.

- [ ] **Step 5: Commit**

```bash
git add admin/src/components/craftmap/useCraftMapState.js admin/src/components/craftmap/panels/PropertiesPanel.jsx
git commit -m "feat(craft-map): recipe nodes follow search/filter, recipe lines show names"
```

---

## Task 6: Final integration — tests, build, live check

- [ ] **Step 1: Full suite**

Run: `npm test`
Expected: all pass. `analysis.errors.test.js` must be green **and unmodified** across this whole plan.

- [ ] **Step 2: Build**

Run: `npm --prefix admin run build`
Expected: success, no new warnings.

- [ ] **Step 3: Live check of the built admin**

Serve (`npm --prefix admin run preview`) and open `http://localhost:4173/panel/`. Without a backend the map has no data, so verify only: the shell mounts, the entry chunk imports cleanly, no new console errors.

Full interactive verification (needs a running backend + owner login), to record as outstanding:
- [ ] Each recipe renders as a `⚗ NN% ×N` node with both ingredients entering it and one edge leaving to the result.
- [ ] The two «Древесина» recipes are now visually distinct, and the panel lists them as `name #id`, not identical emoji strings.
- [ ] Clicking a recipe node opens the recipe panel; delete works and the map refreshes.
- [ ] Clicking an item still highlights the whole chain, now including the recipe nodes.
- [ ] Hiding a category also hides the recipe nodes that touch it — no orphan recipe boxes left floating.
- [ ] Searching an item keeps the producing recipe node highlighted rather than dimmed.
- [ ] Stats still read: Связей 30, Макс. глубина 3, Сред. глубина 1.7, and the same error list as before.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "chore(craft-map): recipe-node integration fixes"
```

---

## Notes for the executor

- Task order is deliberate: Task 1 makes consumers tolerant of `kind: 'recipe'` **before** Task 2 emits any, so no commit leaves the app crashing on `n.item.sorting`.
- `analysis.errors.test.js` is the guard rail for this whole plan. It must pass unmodified at every task. Editing it to make it green defeats the purpose of the change.
- Recipe node positions persist under `r:<id>` keys in the existing `craft_map_positions` table — no schema or endpoint change. Stale rows for deleted recipes are harmless.
- Do not add recipe *editing* (chance/qty/enabled) — only viewing and the existing delete. Editing is a separate backlog item.
