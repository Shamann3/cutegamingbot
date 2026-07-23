# Craft Map — Phase 2 (editing, access gating, layout) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the owner create and delete craft recipes directly on the Craft Map (writing to `craft_recipes` via existing endpoints), restrict the map to owner + desktop only, make the admin content area full-width with a near-fullscreen map, and consolidate the map's visual-state so highlights never get stuck.

**Architecture:** All changes are in the admin React app (`admin/`). Reuse the existing `createContentCraft`/`deleteContentCraft` endpoints — no backend changes. New pure helper modules (visual-state derivation, craft-key generation, tab list) are dependency-free and unit-tested under root vitest. `CraftMapView.jsx` gains a `canEdit` prop and an add-panel/delete flow; its three visual-state effects are replaced by one derivation.

**Tech Stack:** React 18, Vite, `@xyflow/react`, vitest. No new dependencies.

## Global Constraints

- All new/edited frontend code lives under `admin/src/`. Follow existing `panel-*` / `craftmap-*` CSS conventions and Russian UI copy.
- Add/delete write ONLY to `craft_recipes`, via the existing `createContentCraft` / `deleteContentCraft` client wrappers and their endpoints. No backend/schema changes. Do NOT touch the legacy `craft` table.
- The craft model is fixed: exactly 2 ingredients (A, B), each qty 1, one result with `result_qty` output. No N-ingredient / per-edge-quantity changes.
- The Craft Map tab, the "＋ Новый крафт" button, and per-recipe delete buttons are visible ONLY when `role === 'owner'` AND the viewport is desktop. On mobile or for non-owners the map tab must not exist.
- Pure modules used by tests (`viewState.js`, `craftKey.js`, `contentTabs.js`) MUST have zero npm imports so they run under repo-root vitest (`npm test`).
- Existing craftmap graph tests (`buildGraph`, `analysis`) must stay green.
- `createContentCraft` requires a unique `key` and a unique unordered ingredient pair; on violation the backend returns HTTP 400 with a message — surface it as a toast and keep the panel open.

---

## Reference: current `CraftMapView.jsx` shape (before this plan)

Key existing pieces the tasks modify:
- State: `raw`, `nodes/setNodes`, `edges/setEdges`, `selectedId`, `ctxMenu`, `rfRef`.
- `mapState = useCraftMapState(graph)` → `{ query, setQuery, categories, hiddenCategories, toggleCategory, matchedIds, visibleIds }`.
- `chain = useMemo(() => selectedId ? traverseChain(selectedId, graph) : null, …)`.
- THREE visual-state writers to be replaced (Task 2): the search/filter `useEffect` (lines ~61-70), the chain `useEffect` (~80-95), and the imperative `focusItems` (~141-147). `onPaneClick` (~135-139) resets visuals.
- `toFlowEdges` (lines 31-40) sets `data: { recipeId, recipeKey, resultQty }` and `style` from `e.enabled`.
- Render: `<StatsBar/>` then `.craftmap-wrap` containing toolbar, `<ReactFlow>`, `PropertiesPanel`, `ContextMenu`, `ErrorsPanel`.

---

## Task 1: Access gating — role prop, useIsDesktop hook, conditional map tab

**Files:**
- Create: `admin/src/lib/useIsDesktop.js`
- Create: `admin/src/components/craftmap/graph/contentTabs.js`
- Test: `admin/src/components/craftmap/graph/contentTabs.test.js`
- Modify: `admin/src/pages/PanelShell.jsx:262` (pass `role`)
- Modify: `admin/src/pages/sections/ContentSection.jsx` (accept `role`, conditional tabs, guard, pass `canEdit`)

**Interfaces:**
- Produces: `useIsDesktop() -> boolean` (live media-query hook).
- Produces: `contentTabs(canUseMap: boolean) -> Array<{id,label}>` (pure — the TABS list with the map entry included only when `canUseMap`).
- Produces: `<CraftMapView canEdit={boolean} />` will be consumed in later tasks.

- [ ] **Step 1: Write the failing test** (`contentTabs.test.js`)

```javascript
import { describe, it, expect } from 'vitest'
import { contentTabs } from './contentTabs.js'

describe('contentTabs', () => {
  it('omits the map tab when canUseMap is false', () => {
    const ids = contentTabs(false).map((t) => t.id)
    expect(ids).toEqual(['items', 'crops', 'craft', 'quests'])
  })
  it('includes the map tab (before quests) when canUseMap is true', () => {
    const ids = contentTabs(true).map((t) => t.id)
    expect(ids).toEqual(['items', 'crops', 'craft', 'map', 'quests'])
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- contentTabs`
Expected: FAIL — module/function missing.

- [ ] **Step 3: Implement `contentTabs.js`**

```javascript
// Pure. No npm imports.
export function contentTabs(canUseMap) {
  const tabs = [
    { id: 'items', label: 'Предметы' },
    { id: 'crops', label: 'Культуры' },
    { id: 'craft', label: 'Крафт' },
  ]
  if (canUseMap) tabs.push({ id: 'map', label: '🗺 Карта' })
  tabs.push({ id: 'quests', label: 'Задания' })
  return tabs
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- contentTabs`
Expected: PASS (2 tests).

- [ ] **Step 5: Implement `useIsDesktop.js`**

```javascript
import { useEffect, useState } from 'react'

const QUERY = '(min-width: 1024px) and (pointer: fine)'

// Live: true on wide, non-touch (desktop) viewports; updates on resize/orientation.
export function useIsDesktop() {
  const [isDesktop, setIsDesktop] = useState(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return true
    return window.matchMedia(QUERY).matches
  })
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    const mql = window.matchMedia(QUERY)
    const onChange = () => setIsDesktop(mql.matches)
    onChange()
    mql.addEventListener?.('change', onChange)
    return () => mql.removeEventListener?.('change', onChange)
  }, [])
  return isDesktop
}
```

- [ ] **Step 6: Pass `role` from PanelShell to ContentSection**

In `admin/src/pages/PanelShell.jsx`, change line 262 from:
```jsx
          {isContent && <ContentSection />}
```
to:
```jsx
          {isContent && <ContentSection role={role} />}
```

- [ ] **Step 7: Wire conditional tabs + guard + canEdit in ContentSection**

In `admin/src/pages/sections/ContentSection.jsx`:

Add imports near the top (after the existing imports):
```jsx
import { useIsDesktop } from '../../lib/useIsDesktop'
import { contentTabs } from '../../components/craftmap/graph/contentTabs'
```

Delete the module-level `TABS` array (the `const TABS = [ … ]` at lines ~52-58). Its map entry is now conditional.

Change the function signature (line 74) from `export default function ContentSection() {` to:
```jsx
export default function ContentSection({ role = null }) {
```

Inside the component, after the existing `const [tab, setTab] = useState('crops')` (line ~73/75), add:
```jsx
  const isDesktop = useIsDesktop()
  const canUseMap = role === 'owner' && isDesktop
  const TABS = contentTabs(canUseMap)

  // If the map tab becomes unavailable (resize to mobile, or non-owner), leave it.
  useEffect(() => {
    if (tab === 'map' && !canUseMap) setTab('items')
  }, [tab, canUseMap])
```

(The `TABS.map(...)` render at line ~663 now uses this local `TABS`; no change needed there.)

Change the map render (line 1094) from:
```jsx
      {tab === 'map' && <CraftMapView />}
```
to:
```jsx
      {tab === 'map' && canUseMap && <CraftMapView canEdit={canUseMap} />}
```

- [ ] **Step 8: Verify build + tests**

Run: `npm test -- contentTabs` (PASS) and `npm --prefix admin run build` (succeeds).

- [ ] **Step 9: Commit**

```bash
git add admin/src/lib/useIsDesktop.js admin/src/components/craftmap/graph/contentTabs.js admin/src/components/craftmap/graph/contentTabs.test.js admin/src/pages/PanelShell.jsx admin/src/pages/sections/ContentSection.jsx
git commit -m "feat(craft-map): gate map tab to owner + desktop, thread role/canEdit"
```

---

## Task 2: Consolidate visual-state into one pure derivation (fixes stuck highlights)

**Files:**
- Create: `admin/src/components/craftmap/graph/viewState.js`
- Test: `admin/src/components/craftmap/graph/viewState.test.js`
- Modify: `admin/src/components/craftmap/CraftMapView.jsx`

**Interfaces:**
- Produces: `nodeVisual(nodeId, ctx) -> { hidden, dimmed, highlighted, errored }` and `edgeVisual(edgeId, enabled, ctx) -> { animated, opacity, dashed }`.
  - `ctx = { selectedId, chainNodes: Set|null, chainEdges: Set|null, matchedIds: Set, visibleIds: Set, errorFocus: Set|null }`.
  - Precedence for node highlight/dim: errorFocus (if non-empty) → chain (if selectedId) → search (matchedIds). Category filter (`visibleIds`) always sets `hidden`.

- [ ] **Step 1: Write the failing test** (`viewState.test.js`)

```javascript
import { describe, it, expect } from 'vitest'
import { nodeVisual, edgeVisual } from './viewState.js'

const allVisible = new Set(['1', '2', '3'])
const base = { selectedId: null, chainNodes: null, chainEdges: null, matchedIds: new Set(), visibleIds: allVisible, errorFocus: null }

describe('nodeVisual', () => {
  it('is neutral with no selection/search/errors', () => {
    expect(nodeVisual('1', base)).toEqual({ hidden: false, dimmed: false, highlighted: false, errored: false })
  })
  it('hides + dims a node filtered out by category', () => {
    const v = nodeVisual('9', { ...base, visibleIds: allVisible })
    expect(v.hidden).toBe(true)
    expect(v.dimmed).toBe(true)
  })
  it('search: highlights matches, dims the rest', () => {
    const ctx = { ...base, matchedIds: new Set(['1']) }
    expect(nodeVisual('1', ctx)).toMatchObject({ highlighted: true, dimmed: false })
    expect(nodeVisual('2', ctx)).toMatchObject({ highlighted: false, dimmed: true })
  })
  it('chain takes precedence over search', () => {
    const ctx = { ...base, selectedId: '1', chainNodes: new Set(['1', '2']), matchedIds: new Set(['3']) }
    expect(nodeVisual('1', ctx)).toMatchObject({ highlighted: true, dimmed: false })
    expect(nodeVisual('2', ctx)).toMatchObject({ dimmed: false })
    expect(nodeVisual('3', ctx)).toMatchObject({ dimmed: true, highlighted: false })
  })
  it('errorFocus takes precedence over chain and search', () => {
    const ctx = { ...base, selectedId: '1', chainNodes: new Set(['1', '2']), errorFocus: new Set(['3']) }
    expect(nodeVisual('3', ctx)).toMatchObject({ errored: true, dimmed: false })
    expect(nodeVisual('1', ctx)).toMatchObject({ errored: false, dimmed: true })
  })
})

describe('edgeVisual', () => {
  it('dashes disabled edges, full opacity when no chain', () => {
    expect(edgeVisual('10:a', false, base)).toMatchObject({ dashed: true, opacity: 0.6, animated: false })
  })
  it('animates chain edges and dims the rest when a chain is active', () => {
    const ctx = { ...base, selectedId: '1', chainEdges: new Set(['10:a']) }
    expect(edgeVisual('10:a', true, ctx)).toMatchObject({ animated: true, opacity: 1 })
    expect(edgeVisual('11:a', true, ctx)).toMatchObject({ animated: false, opacity: 0.12 })
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- viewState`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `viewState.js`**

```javascript
// Pure derivation of node/edge visual flags. No npm imports.

export function nodeVisual(nodeId, ctx) {
  const id = String(nodeId)
  const hidden = !ctx.visibleIds.has(id)
  let dimmed = false
  let highlighted = false
  let errored = false

  if (ctx.errorFocus && ctx.errorFocus.size > 0) {
    errored = ctx.errorFocus.has(id)
    dimmed = !errored
  } else if (ctx.selectedId && ctx.chainNodes) {
    highlighted = id === String(ctx.selectedId)
    dimmed = !ctx.chainNodes.has(id)
  } else if (ctx.matchedIds && ctx.matchedIds.size > 0) {
    highlighted = ctx.matchedIds.has(id)
    dimmed = !highlighted
  }

  return { hidden, dimmed: dimmed || hidden, highlighted, errored }
}

export function edgeVisual(edgeId, enabled, ctx) {
  const chainActive = !!(ctx.selectedId && ctx.chainEdges)
  const inChain = ctx.chainEdges ? ctx.chainEdges.has(edgeId) : false
  let opacity = enabled === false ? 0.6 : 1
  if (chainActive && !inChain) opacity = 0.12
  return { animated: inChain, opacity, dashed: enabled === false }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- viewState`
Expected: PASS.

- [ ] **Step 5: Refactor `CraftMapView.jsx` to a single derivation**

In `admin/src/components/craftmap/CraftMapView.jsx`:

(a) Add the import (with the other graph imports, line ~10):
```jsx
import { nodeVisual, edgeVisual } from './graph/viewState'
```

(b) In `toFlowEdges` (lines 31-40), add `enabled` to edge `data` so the derivation can read it. Change the returned object's `data` to:
```jsx
    data: { recipeId: e.recipeId, recipeKey: e.recipeKey, resultQty: e.resultQty, enabled: e.enabled },
```

(c) Add `errorFocus` state next to `selectedId` (line ~53):
```jsx
  const [errorFocus, setErrorFocus] = useState(null) // Set<string> | null
```

(d) DELETE the search/filter `useEffect` (lines ~61-70) and the chain `useEffect` (lines ~80-95). Replace BOTH with a single derivation effect placed after `chain`/`errors`/`stats` are defined:
```jsx
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
```

(e) Replace `focusItems` (lines ~141-147) body with just state changes:
```jsx
  const focusItems = useCallback((itemIds) => {
    setSelectedId(null)
    setErrorFocus(new Set(itemIds.map(String)))
  }, [])
```

(f) Update `onNodeClick` (line ~134) to clear error focus:
```jsx
  const onNodeClick = useCallback((_evt, node) => { setErrorFocus(null); setSelectedId(node.id) }, [])
```

(g) Replace `onPaneClick` (lines ~135-139) — clearing selection + error focus is enough; the derivation effect re-derives from search/filter automatically:
```jsx
  const onPaneClick = useCallback(() => {
    setSelectedId(null)
    setErrorFocus(null)
  }, [])
```

- [ ] **Step 6: Verify build + full pure-module suite**

Run: `npm test -- craftmap` (all graph + viewState tests PASS) and `npm --prefix admin run build` (succeeds).

- [ ] **Step 7: Commit**

```bash
git add admin/src/components/craftmap/graph/viewState.js admin/src/components/craftmap/graph/viewState.test.js admin/src/components/craftmap/CraftMapView.jsx
git commit -m "refactor(craft-map): single visual-state derivation (no stuck highlights)"
```

---

## Task 3: Add craft — AddCraftPanel + toolbar button

**Files:**
- Create: `admin/src/components/craftmap/graph/craftKey.js`
- Test: `admin/src/components/craftmap/graph/craftKey.test.js`
- Create: `admin/src/components/craftmap/panels/AddCraftPanel.jsx`
- Modify: `admin/src/components/craftmap/CraftMapView.jsx` (button + panel, gated by `canEdit`)
- Modify: `admin/src/index.css` (append `.craftmap-add` styles)

**Interfaces:**
- Consumes: `createContentCraft` (adminClient), `DexItemSearchPicker`, `notifyAdmin`.
- Produces: `makeCraftKey(resultId, ingAId, ingBId) -> string` matching `^[a-z][a-z0-9_]{1,48}$`.
- Produces: `AddCraftPanel({ onClose, onCreated })`.

- [ ] **Step 1: Write the failing test** (`craftKey.test.js`)

```javascript
import { describe, it, expect } from 'vitest'
import { makeCraftKey } from './craftKey.js'

const RE = /^[a-z][a-z0-9_]{1,48}$/

describe('makeCraftKey', () => {
  it('produces a backend-valid key', () => {
    expect(makeCraftKey('3', '7', '9')).toMatch(RE)
  })
  it('is order-independent in the ingredient pair', () => {
    expect(makeCraftKey('3', '7', '9')).toBe(makeCraftKey('3', '9', '7'))
  })
  it('always starts with a letter even for numeric ids', () => {
    expect(makeCraftKey('300', '301', '302')[0]).toMatch(/[a-z]/)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- craftKey`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `craftKey.js`**

```javascript
// Pure. No npm imports. Deterministic, order-independent, backend-valid key.
export function makeCraftKey(resultId, ingAId, ingBId) {
  const pair = [String(ingAId), String(ingBId)].sort()
  let key = `map_${resultId}_${pair[0]}_${pair[1]}`
    .toLowerCase()
    .replace(/[^a-z0-9_]/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '')
  if (!/^[a-z]/.test(key)) key = `k_${key}`
  return key.slice(0, 49)
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- craftKey`
Expected: PASS.

- [ ] **Step 5: Implement `AddCraftPanel.jsx`**

```jsx
import { useState } from 'react'
import DexItemSearchPicker from '../../DexItemSearchPicker'
import { createContentCraft } from '../../../lib/adminClient'
import { notifyAdmin } from '../../../lib/notify'
import { makeCraftKey } from '../graph/craftKey'

export default function AddCraftPanel({ onClose, onCreated }) {
  const [resultId, setResultId] = useState('')
  const [ingA, setIngA] = useState('')
  const [ingB, setIngB] = useState('')
  const [successPercent, setSuccessPercent] = useState('100')
  const [resultQty, setResultQty] = useState('1')
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!resultId || !ingA || !ingB) { notifyAdmin('Выберите все три предмета', { error: true }); return }
    if (ingA === ingB) { notifyAdmin('Ингредиенты A и B должны быть разными', { error: true }); return }
    setSaving(true)
    try {
      await createContentCraft({
        key: makeCraftKey(resultId, ingA, ingB),
        displayName: '',
        resultItemId: resultId,
        ingredientAId: ingA,
        ingredientBId: ingB,
        successPercent: Math.max(1, Math.min(100, parseInt(successPercent, 10) || 100)),
        enabled: true,
        remains: 0,
        resultQty: Math.max(1, parseInt(resultQty, 10) || 1),
      })
      notifyAdmin('Крафт создан')
      onCreated()
    } catch (err) {
      notifyAdmin(err?.message || 'Не удалось создать крафт', { error: true })
    } finally {
      setSaving(false)
    }
  }

  return (
    <aside className="craftmap-add">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 className="panel-users-subtitle" style={{ margin: 0 }}>＋ Новый крафт</h3>
        <button className="pu-close-btn" onClick={onClose}>✕</button>
      </div>
      <p className="panel-shelf-label">Результат</p>
      <DexItemSearchPicker label="Предмет на выходе" value={resultId} onChange={setResultId} />
      <p className="panel-shelf-label" style={{ marginTop: 8 }}>Ингредиент A</p>
      <DexItemSearchPicker label="Первый" value={ingA} onChange={setIngA} />
      <p className="panel-shelf-label" style={{ marginTop: 8 }}>Ингредиент B</p>
      <DexItemSearchPicker label="Второй" value={ingB} onChange={setIngB} />
      <div className="panel-content-inline-2" style={{ marginTop: 10 }}>
        <label className="panel-economy-field">
          <span>Шанс %</span>
          <input className="panel-users-input" type="number" min={1} max={100} value={successPercent}
            onChange={(e) => setSuccessPercent(e.target.value.replace(/[^\d]/g, ''))} />
        </label>
        <label className="panel-economy-field">
          <span>Кол-во на выходе</span>
          <input className="panel-users-input" type="number" min={1} value={resultQty}
            onChange={(e) => setResultQty(e.target.value.replace(/[^\d]/g, ''))} />
        </label>
      </div>
      <div className="panel-content-form-actions" style={{ marginTop: 12 }}>
        <button className="panel-users-btn panel-users-btn-primary" disabled={saving} onClick={submit}>
          {saving ? 'Создаём…' : 'Создать'}
        </button>
        <button className="panel-users-btn" onClick={onClose}>Отмена</button>
      </div>
    </aside>
  )
}
```

- [ ] **Step 6: Wire into `CraftMapView.jsx`**

Change the signature (line 42) to accept `canEdit`:
```jsx
export default function CraftMapView({ canEdit = false }) {
```
Add import (with the panel imports, ~line 15):
```jsx
import AddCraftPanel from './panels/AddCraftPanel'
```
Add state (near `showAdd`, after `ctxMenu` line ~54):
```jsx
  const [showAdd, setShowAdd] = useState(false)
```
In the toolbar (inside `.craftmap-toolbar`, after the "Обновить" button, ~line 198), add the gated button:
```jsx
          {canEdit ? <button className="panel-users-btn panel-users-btn-primary" onClick={() => setShowAdd(true)}>＋ Новый крафт</button> : null}
```
Render the panel inside `.craftmap-wrap` (after the `ContextMenu` render, ~line 228):
```jsx
        {showAdd ? <AddCraftPanel onClose={() => setShowAdd(false)} onCreated={() => { setShowAdd(false); load() }} /> : null}
```

- [ ] **Step 7: Append `.craftmap-add` styles to `admin/src/index.css`**

```css
/* Add-craft panel — mirrors .craftmap-props placement (right side) */
.craftmap-add { position: absolute; top: 0; right: 0; height: 100%; width: 340px; z-index: 8;
  background: rgba(16,19,26,.98); border-left: 1px solid rgba(255,255,255,.08);
  box-shadow: -12px 0 30px rgba(0,0,0,.45); overflow-y: auto; padding: 16px; }
[data-theme="light"] .craftmap-add { background: #ffffff; color: #1a2230; }
```

- [ ] **Step 8: Verify build + tests**

Run: `npm test -- craftKey` (PASS) and `npm --prefix admin run build` (succeeds).

- [ ] **Step 9: Commit**

```bash
git add admin/src/components/craftmap/graph/craftKey.js admin/src/components/craftmap/graph/craftKey.test.js admin/src/components/craftmap/panels/AddCraftPanel.jsx admin/src/components/craftmap/CraftMapView.jsx admin/src/index.css
git commit -m "feat(craft-map): create recipes from the map via add panel"
```

---

## Task 4: Delete craft — per-recipe delete in PropertiesPanel

**Files:**
- Modify: `admin/src/components/craftmap/panels/PropertiesPanel.jsx` (add `canEdit` + `onDeleteRecipe`, 🗑 per recipe)
- Modify: `admin/src/components/craftmap/CraftMapView.jsx` (confirm modal + delete flow, pass props)
- Modify: `admin/src/index.css` (append `.craftmap-recipe-row` styles)

**Interfaces:**
- Consumes: `deleteContentCraft` (adminClient), `AdminActionModal`.
- Produces: `PropertiesPanel({ item, graph, onClose, onGoTo, canEdit, onDeleteRecipe })` — renders a 🗑 button next to each "Рецепты создания" recipe when `canEdit`, calling `onDeleteRecipe(recipe)`.

- [ ] **Step 1: Modify `PropertiesPanel.jsx`**

Change the signature (line 1):
```jsx
export default function PropertiesPanel({ item, graph, onClose, onGoTo, canEdit = false, onDeleteRecipe }) {
```
Replace the "Рецепты создания" list block (lines 22-25) with a row layout that adds the delete button:
```jsx
      <h4 className="panel-shelf-label" style={{ marginTop: 14 }}>Рецепты создания ({producedBy.length})</h4>
      {producedBy.length ? producedBy.map((r) => (
        <div key={r.id} className="craftmap-recipe-row">
          <span className="panel-shelf-muted">{recipeLine(r)}</span>
          {canEdit ? (
            <button className="craftmap-recipe-del" title="Удалить рецепт" onClick={() => onDeleteRecipe && onDeleteRecipe(r)}>🗑</button>
          ) : null}
        </div>
      )) : <p className="panel-shelf-muted">— базовый ресурс —</p>}
```

- [ ] **Step 2: Wire delete flow in `CraftMapView.jsx`**

Add imports (deleteContentCraft with the adminClient import line 6; AdminActionModal with component imports):
```jsx
import { fetchCraftMap, saveCraftMapPositions, deleteContentCraft } from '../../lib/adminClient'
import AdminActionModal from '../../AdminActionModal'
```
Add state (after `showAdd`):
```jsx
  const [deleteTarget, setDeleteTarget] = useState(null) // recipe object | null
```
Add the confirm handler (near the other callbacks):
```jsx
  const confirmDelete = useCallback(async () => {
    if (!deleteTarget) return
    try {
      await deleteContentCraft(deleteTarget.id)
      notifyAdmin('Крафт удалён')
      setDeleteTarget(null)
      setSelectedId(null)
      await load()
    } catch (err) {
      notifyAdmin(err?.message || 'Не удалось удалить крафт', { error: true })
    }
  }, [deleteTarget, load])
```
Pass the new props to `PropertiesPanel` (line ~226):
```jsx
        {selectedItem ? (
          <PropertiesPanel item={selectedItem} graph={graph} onClose={onPaneClick} onGoTo={goTo}
            canEdit={canEdit} onDeleteRecipe={(r) => setDeleteTarget(r)} />
        ) : null}
```
Render the confirm modal inside `.craftmap-wrap` (after the AddCraftPanel render):
```jsx
        {deleteTarget ? (
          <AdminActionModal open danger
            title={`Удалить рецепт «${deleteTarget.displayName || deleteTarget.key}»?`}
            description="Рецепт будет удалён из craft_recipes и сразу исчезнет из игры."
            confirmText="Удалить"
            onConfirm={confirmDelete}
            onCancel={() => setDeleteTarget(null)} />
        ) : null}
```

- [ ] **Step 3: Append `.craftmap-recipe-row` styles to `admin/src/index.css`**

```css
.craftmap-recipe-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 2px; }
.craftmap-recipe-del { background: none; border: 0; cursor: pointer; font-size: 14px; opacity: .7; padding: 2px 4px; border-radius: 6px; }
.craftmap-recipe-del:hover { opacity: 1; background: rgba(255,80,80,.15); }
```

- [ ] **Step 4: Verify build**

Run: `npm --prefix admin run build`
Expected: succeeds.

- [ ] **Step 5: Commit**

```bash
git add admin/src/components/craftmap/panels/PropertiesPanel.jsx admin/src/components/craftmap/CraftMapView.jsx admin/src/index.css
git commit -m "feat(craft-map): delete recipes from the properties panel"
```

---

## Task 5: Layout — full-width content + near-fullscreen map

**Files:**
- Modify: `admin/src/index.css` (`.panel-layout-content` width, `.craftmap-wrap` height)

**Interfaces:** none (CSS only).

- [ ] **Step 1: Make the content layout full-width**

In `admin/src/index.css`, the `.panel-layout-content` rule (line 2729) is `display: grid; grid-template-columns: minmax(12.5rem, 15%) minmax(0, 1fr); gap: .85rem; align-items: start;`. Add a full-width override so it is not capped at the base `.panel-layout` `min(100%, 88rem)`:

```css
.panel-layout-content {
  display: grid;
  grid-template-columns: minmax(12.5rem, 15%) minmax(0, 1fr);
  gap: 0.85rem;
  align-items: start;
  width: 100%;
  max-width: none;
}
```

(Add the `width: 100%; max-width: none;` lines; keep the existing grid declarations.)

- [ ] **Step 2: Make the map fill the content area**

Change the `.craftmap-wrap` rule (line 11987) height from `72vh` to a near-fullscreen height:

```css
.craftmap-wrap { position: relative; width: 100%; height: calc(100dvh - 12rem); min-height: 560px;
  border-radius: 18px; overflow: hidden; border: 1px solid var(--panel-border, rgba(255,255,255,.08));
  background: var(--panel-bg, #0e1117); }
```

(Only the `height` value changes — from `72vh` to `calc(100dvh - 12rem)` — and `min-height` from `520px` to `560px`. Keep the rest.)

- [ ] **Step 3: Verify build**

Run: `npm --prefix admin run build`
Expected: succeeds.

- [ ] **Step 4: Commit**

```bash
git add admin/src/index.css
git commit -m "feat(craft-map): full-width content area and near-fullscreen map"
```

---

## Task 6: Final integration — tests, build, live browser verification

**Files:** none unless fixes are needed.

- [ ] **Step 1: Full pure-module suite**

Run: `npm test`
Expected: all pass, including new `contentTabs`, `viewState`, `craftKey` and existing `buildGraph`/`analysis` tests.

- [ ] **Step 2: Production build**

Run: `npm --prefix admin run build`
Expected: succeeds, no circular-chunk warning, no errors.

- [ ] **Step 3: Live browser verification (controller runs the built admin)**

Serve the build (`npm --prefix admin run preview`) and open `http://localhost:4173/panel/` in the browser. Because there is no backend, data won't load — but verify what is checkable without a backend, and note anything needing a live backend:
- The admin shell mounts (auth screen), no console/module errors.
- Build-level: the new modules resolve (no import errors in console).

Full interactive verification (with a running backend + owner login) — to be done against the deployed/staging admin:
- [ ] «🗺 Карта» tab visible for owner on desktop; absent when the window is narrowed below 1024px (resize) and (by role) for non-owners; auto-fallback to «Предметы» when it disappears.
- [ ] «＋ Новый крафт» → pick result + 2 ingredients + chance/qty → Создать → new recipe appears on the map, stats increment; duplicate pair → error toast, panel stays open.
- [ ] Select the result item → «Рецепты создания» shows 🗑 → confirm → recipe disappears from the map.
- [ ] Content area spans full width; map is near-fullscreen; light/dark theme both fine.
- [ ] Highlights don't stick: search → click node (chain) → click pane → search dimming restored; click an error → focus; click pane → cleared.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "chore(craft-map): phase 2 integration fixes"
```

---

## Notes for the executor

- No backend changes: `createContentCraft`/`deleteContentCraft` and their endpoints already exist and target `craft_recipes`. Do not add endpoints or touch `server/`.
- Keep `viewState.js`, `craftKey.js`, `contentTabs.js` free of npm imports so their colocated `*.test.js` run under root `npm test`.
- The map tab only renders when `canUseMap` (owner + desktop), so inside `CraftMapView` `canEdit` is effectively always true when mounted — but thread it explicitly for correctness and so the add/delete controls are self-gating.
- `DexItemSearchPicker` props are `{ label, value, onChange }` where `onChange(idString)`.
- After add/delete, call `load()` to refetch — nodes, edges, stats, and errors all recompute from fresh data.
