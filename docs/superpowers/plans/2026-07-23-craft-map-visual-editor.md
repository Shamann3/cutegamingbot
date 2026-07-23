# Craft Map (Phase 1: read-only) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only interactive node-graph "Craft Map" tab to the admin panel that visualizes all dex items as cards and all craft recipes as edges, with pan/zoom/minimap, search, filters, chain highlighting, a properties panel, a context menu, error detection, and stats — persisting node positions to the database.

**Architecture:** New React Flow canvas mounted as a "Карта" tab inside `admin/src/pages/sections/ContentSection.jsx`. Pure, dependency-free JS modules derive the graph model, run analysis (chain traversal, error detection, stats), and lay out nodes (dagre). A single new FastAPI endpoint returns items + recipes + saved positions in one payload; a second endpoint batch-upserts positions into a new `craft_map_positions` table.

**Tech Stack:** React 18, Vite, `@xyflow/react` v12 (React Flow), `@dagrejs/dagre`, Python FastAPI + asyncpg (Postgres), vitest.

## Global Constraints

- Admin frontend code lives under `admin/src/`; components in `admin/src/components/`, sections in `admin/src/pages/sections/`, API wrappers in `admin/src/lib/adminClient.js`. Follow the existing `panel-*` / `craftmap-*` CSS class convention in `admin/src/index.css`.
- Backend business logic goes in `server/admin_content.py`; routes in `server/admin_routes.py` guarded by `require_admin_permission("manage_content")`; schema in `server/schema.sql` via `CREATE TABLE IF NOT EXISTS`.
- The craft model is fixed: exactly 2 ingredients (`ingredient_a_id`, `ingredient_b_id`), each quantity 1, one result (`result_qty` output). Do NOT change this model in Phase 1. The map is read-only for recipes; only node positions are writable.
- Item metadata maps to existing fields only: emoji = image, `sorting` = category/chain. Do NOT add rarity/level/image/category fields to `dex`.
- Pure graph modules (`buildGraph.js`, `analysis.js`) MUST have zero external/npm imports so they run under the repo-root vitest (`npm test`). Only `layout.js` may import `@dagrejs/dagre`.
- All user-facing copy is Russian, matching the existing admin UI.
- The existing `CraftRecipeWizard` and the `craft` tab remain untouched and functional.

---

## Data Shapes (referenced by multiple tasks)

**`GET /content/craft-map` response:**
```json
{
  "items": [
    { "id": "23", "name": "Бумага", "name1": "", "emoji": "📄",
      "price": 100, "sorting": "ресурсы", "bio": "…", "use": "", "bonus": "" }
  ],
  "recipes": [
    { "id": 1, "key": "paper_craft", "displayName": "Бумага",
      "resultItemId": "23", "resultName": "Бумага", "resultEmoji": "📄",
      "ingredientAId": "7", "ingredientAName": "Бревно", "ingredientAEmoji": "🪵",
      "ingredientBId": "9", "ingredientBName": "Вода", "ingredientBEmoji": "💧",
      "successPercent": 100, "enabled": true, "remains": 0, "resultQty": 1 }
  ],
  "positions": { "23": { "x": 120.0, "y": -40.0 } }
}
```
`item.id` and all recipe id references are **strings** (except `recipe.id`, `successPercent`, `remains`, `resultQty`, `price` which are numbers). `recipe.id` is a number.

**Graph model produced by `buildGraph(items, recipes, opts)`** (see Task 3 for exact code):
```
{
  nodes: [{ id: string, item: ItemObj }],          // ItemObj may have missing:true if only referenced, never defined
  edges: [{ id, source, target, recipeId, recipeKey, slot, successPercent, resultQty, enabled }],
  index: {
    itemsById: Map<string, ItemObj>,               // real items only (as passed in)
    recipesById: Map<number, RecipeObj>,
    producedBy: Map<string, number[]>,              // itemId -> recipeIds whose result is itemId
    usedIn: Map<string, number[]>,                  // itemId -> recipeIds that consume itemId
    forward: Map<string, Set<string>>,              // ingredientId -> Set(resultId)  (downstream)
    backward: Map<string, Set<string>>              // resultId -> Set(ingredientId)  (upstream)
  }
}
```
`edge.id = `${recipeId}:${slot}``, `slot ∈ {'a','b'}`, `edge.source` = ingredient id, `edge.target` = result id.

---

## Task 1: Backend — positions table, craft-map endpoints, pure helper

**Files:**
- Modify: `server/schema.sql` (append new table near `craft_recipes`, around line 168)
- Create: `server/craft_map.py`
- Modify: `server/admin_content.py` (add functions; import the helper)
- Modify: `server/admin_routes.py` (add Pydantic body, 2 routes, extend the `admin_content` import block at line 175)
- Test: `tests/test_craft_map_positions.py`

**Interfaces:**
- Produces (Python): `craft_map.serialize_positions(rows) -> dict[str, dict]`; `admin_content.get_craft_map() -> dict`; `admin_content.save_craft_map_positions(positions: list[dict], *, admin_user_id: int) -> dict`.
- Produces (HTTP): `GET /content/craft-map`, `POST /content/craft-map/positions`.

- [ ] **Step 1: Write the failing test** (`tests/test_craft_map_positions.py`)

```python
"""Проверка сериализации позиций карты крафта (чистый хелпер, без БД)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from craft_map import serialize_positions


def test_serialize_positions_maps_rows_to_dict():
    rows = [
        {"item_id": 5, "x": 10.0, "y": -3.5},
        {"item_id": "12", "x": 0.0, "y": 0.0},
    ]
    assert serialize_positions(rows) == {
        "5": {"x": 10.0, "y": -3.5},
        "12": {"x": 0.0, "y": 0.0},
    }


def test_serialize_positions_empty():
    assert serialize_positions([]) == {}


if __name__ == "__main__":
    test_serialize_positions_maps_rows_to_dict()
    test_serialize_positions_empty()
    print("ok")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_craft_map_positions.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'craft_map'`

- [ ] **Step 3: Create `server/craft_map.py`**

```python
"""Чистые хелперы карты крафта (без БД, для тестируемости)."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def serialize_positions(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, float]]:
    """Строки craft_map_positions -> {itemId: {x, y}}."""
    out: dict[str, dict[str, float]] = {}
    for row in rows:
        item_id = str(row["item_id"])
        out[item_id] = {"x": float(row["x"]), "y": float(row["y"])}
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_craft_map_positions.py`
Expected: `ok`

- [ ] **Step 5: Add the table to `server/schema.sql`**

Insert after the `craft_recipes` block (after line 173, before the `content_migrations` comment at line 175):

```sql
-- Координаты карточек предметов в визуальном редакторе крафта (общие для всех админов).
CREATE TABLE IF NOT EXISTS craft_map_positions (
    item_id     TEXT PRIMARY KEY,
    x           DOUBLE PRECISION NOT NULL,
    y           DOUBLE PRECISION NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by  BIGINT
);
```

- [ ] **Step 6: Add backend functions to `server/admin_content.py`**

At the top, extend the import from `craft_map` (add after line 15 `from dex_catalog import dex_catalog`):

```python
from craft_map import serialize_positions
```

Append these functions at the end of the file:

```python
async def get_craft_map() -> dict:
    """Данные для визуального редактора: предметы, рецепты, сохранённые позиции."""
    from content_registry import all_craft_recipes, ensure_content_registry_loaded

    await ensure_content_registry_loaded(db.pool)
    recipes = [recipe_to_admin_dict(recipe) for recipe in all_craft_recipes()]

    rows = await db.pool.fetch(
        'SELECT id, name, name1, emoji, price, sorting, bio, "use", bonus FROM dex ORDER BY id ASC'
    )
    items = []
    for row in rows:
        item_id = str(row["id"])
        items.append(
            {
                "id": item_id,
                "name": (row["name"] or "").strip() or item_id,
                "name1": (row["name1"] or "").strip(),
                "emoji": (row["emoji"] or "").strip() or "📦",
                "price": int(row["price"] or 0),
                "sorting": row["sorting"],
                "bio": (row["bio"] or "").strip(),
                "use": str(row["use"] or "").strip() if row["use"] not in (None, 0) else "",
                "bonus": str(row["bonus"] or "").strip() if row["bonus"] not in (None, 0) else "",
            }
        )

    pos_rows = await db.pool.fetch("SELECT item_id, x, y FROM craft_map_positions")
    positions = serialize_positions(pos_rows)

    return {"items": items, "recipes": recipes, "positions": positions}


async def save_craft_map_positions(positions: list[dict], *, admin_user_id: int) -> dict:
    """Батч-upsert координат карточек."""
    args = []
    for pos in positions or []:
        item_id = str(pos.get("itemId", "")).strip()
        if not item_id:
            continue
        try:
            x = float(pos["x"])
            y = float(pos["y"])
        except (KeyError, TypeError, ValueError):
            continue
        args.append((item_id, x, y, admin_user_id))

    if not args:
        return {"saved": 0}

    await db.pool.executemany(
        """
        INSERT INTO craft_map_positions (item_id, x, y, updated_by, updated_at)
        VALUES ($1, $2, $3, $4, NOW())
        ON CONFLICT (item_id) DO UPDATE
            SET x = EXCLUDED.x,
                y = EXCLUDED.y,
                updated_by = EXCLUDED.updated_by,
                updated_at = NOW()
        """,
        args,
    )
    return {"saved": len(args)}
```

- [ ] **Step 7: Add the Pydantic body + routes to `server/admin_routes.py`**

Extend the `admin_content` import block (lines 175-188) to add the two new functions:

```python
from admin_content import (
    create_craft_recipe,
    create_crop,
    create_dex_item,
    delete_craft_recipe,
    delete_crop,
    delete_dex_item,
    get_content_overview,
    get_craft_map,
    get_dex_item_full,
    list_dex_items_admin,
    save_craft_map_positions,
    update_craft_recipe,
    update_crop,
    update_dex_item_meta,
)
```

Add a Pydantic model near the other content bodies (after `DexItemMetaBody`, around line 550):

```python
class CraftMapPositionItem(BaseModel):
    itemId: str = Field(min_length=1, max_length=64)
    x: float
    y: float
    model_config = {"extra": "forbid"}


class CraftMapPositionsBody(BaseModel):
    positions: list[CraftMapPositionItem] = Field(default_factory=list, max_length=5000)
    model_config = {"extra": "forbid"}
```

Add the two routes next to the other `/content/*` routes (after the craft routes, around line 2870):

```python
@router.get("/content/craft-map")
async def admin_content_craft_map(
    _admin_id: int = Depends(require_admin_permission("manage_content")),
):
    return await get_craft_map()


@router.post("/content/craft-map/positions")
async def admin_content_craft_map_positions(
    body: CraftMapPositionsBody,
    admin_id: int = Depends(require_admin_permission("manage_content")),
):
    positions = [p.model_dump() for p in body.positions]
    return await save_craft_map_positions(positions, admin_user_id=admin_id)
```

- [ ] **Step 8: Manual smoke test (requires running server + admin token)**

Run (replace `<TOKEN>` and base URL with your local admin API):
```bash
curl -s -H "Authorization: Bearer <TOKEN>" http://127.0.0.1:8000/api/admin/content/craft-map | head -c 400
```
Expected: JSON object with `items`, `recipes`, `positions` keys. `positions` is `{}` on a fresh table.

- [ ] **Step 9: Commit**

```bash
git add server/schema.sql server/craft_map.py server/admin_content.py server/admin_routes.py tests/test_craft_map_positions.py
git commit -m "feat(craft-map): backend positions table and craft-map endpoints"
```

---

## Task 2: Admin dependencies + API client wrappers

**Files:**
- Modify: `admin/package.json` (add dependencies)
- Modify: `admin/src/lib/adminClient.js` (add two wrappers near the other `content` wrappers, ~line 1224)

**Interfaces:**
- Consumes: `GET /content/craft-map`, `POST /content/craft-map/positions` (Task 1).
- Produces (JS): `fetchCraftMap() -> Promise<{items, recipes, positions}>`; `saveCraftMapPositions(positions: Array<{itemId,x,y}>) -> Promise<{saved:number}>`.

- [ ] **Step 1: Install React Flow + dagre into the admin package**

Run:
```bash
npm --prefix admin install @xyflow/react@^12 @dagrejs/dagre@^1
```
Expected: `admin/package.json` gains both under `dependencies`; `admin/package-lock.json` updates.

- [ ] **Step 2: Verify the install**

Run:
```bash
node -e "require('admin/node_modules/@xyflow/react/package.json'); require('admin/node_modules/@dagrejs/dagre/package.json'); console.log('ok')"
```
Expected: `ok`

- [ ] **Step 3: Add client wrappers to `admin/src/lib/adminClient.js`**

Insert after `deleteContentCraft` (line 1224):

```javascript
export async function fetchCraftMap() {
  return adminFetch('/content/craft-map')
}

export async function saveCraftMapPositions(positions) {
  return adminFetch('/content/craft-map/positions', {
    method: 'POST',
    body: { positions },
  })
}
```

- [ ] **Step 4: Verify the admin app still builds**

Run:
```bash
npm --prefix admin run build
```
Expected: build succeeds (no import errors).

- [ ] **Step 5: Commit**

```bash
git add admin/package.json admin/package-lock.json admin/src/lib/adminClient.js
git commit -m "feat(craft-map): add react-flow/dagre deps and api client wrappers"
```

---

## Task 3: `buildGraph.js` — derive graph model from items + recipes (TDD)

**Files:**
- Create: `admin/src/components/craftmap/graph/buildGraph.js`
- Test: `admin/src/components/craftmap/graph/buildGraph.test.js`

**Interfaces:**
- Consumes: items + recipes from the API (Data Shapes section).
- Produces: `buildGraph(items, recipes, { includeOrphans = false } = {}) -> { nodes, edges, index }` (exact shape in Data Shapes section). Placeholder items for referenced-but-undefined ids carry `missing: true`.

- [ ] **Step 1: Write the failing test** (`buildGraph.test.js`)

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

describe('buildGraph', () => {
  it('creates a node per referenced item and skips orphans by default', () => {
    const g = buildGraph(items, recipes)
    const ids = g.nodes.map((n) => n.id).sort()
    expect(ids).toEqual(['1', '2', '3'])
  })

  it('includes orphan items when includeOrphans is true', () => {
    const g = buildGraph(items, recipes, { includeOrphans: true })
    expect(g.nodes.map((n) => n.id).sort()).toEqual(['1', '2', '3', '9'])
  })

  it('creates two edges per recipe (a->result, b->result) with stable ids', () => {
    const g = buildGraph(items, recipes)
    const byId = Object.fromEntries(g.edges.map((e) => [e.id, e]))
    expect(g.edges).toHaveLength(2)
    expect(byId['10:a']).toMatchObject({ source: '1', target: '3', slot: 'a', resultQty: 2, enabled: true })
    expect(byId['10:b']).toMatchObject({ source: '2', target: '3', slot: 'b' })
  })

  it('builds producedBy / usedIn / forward / backward indexes', () => {
    const g = buildGraph(items, recipes)
    expect(g.index.producedBy.get('3')).toEqual([10])
    expect(g.index.usedIn.get('1')).toEqual([10])
    expect([...g.index.forward.get('1')]).toEqual(['3'])
    expect([...g.index.backward.get('3')].sort()).toEqual(['1', '2'])
  })

  it('creates placeholder nodes marked missing for undefined referenced items', () => {
    const g = buildGraph([{ id: '3', name: 'Бумага', emoji: '📄' }], recipes)
    const one = g.nodes.find((n) => n.id === '1')
    expect(one).toBeDefined()
    expect(one.item.missing).toBe(true)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- buildGraph`
Expected: FAIL — cannot find module `./buildGraph.js` / `buildGraph is not a function`.

- [ ] **Step 3: Implement `buildGraph.js`**

```javascript
// Pure graph derivation. NO external imports (must run under root vitest).

function pushMap(map, key, value) {
  const arr = map.get(key)
  if (arr) arr.push(value)
  else map.set(key, [value])
}

function addSet(map, key, value) {
  const set = map.get(key)
  if (set) set.add(value)
  else map.set(key, new Set([value]))
}

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

  const ensureItem = (id) => {
    const key = String(id)
    if (itemsById.has(key)) return itemsById.get(key)
    return { id: key, name: key, emoji: '❓', sorting: null, missing: true }
  }

  for (const recipe of recipes || []) {
    const rid = recipe.id
    recipesById.set(rid, recipe)
    const result = String(recipe.resultItemId)
    const slots = [
      ['a', String(recipe.ingredientAId)],
      ['b', String(recipe.ingredientBId)],
    ]
    referenced.add(result)
    for (const [slot, ing] of slots) {
      referenced.add(ing)
      edges.push({
        id: `${rid}:${slot}`,
        source: ing,
        target: result,
        recipeId: rid,
        recipeKey: recipe.key,
        slot,
        successPercent: recipe.successPercent,
        resultQty: recipe.resultQty,
        enabled: recipe.enabled !== false,
      })
      pushMap(usedIn, ing, rid)
      addSet(forward, ing, result)
      addSet(backward, result, ing)
    }
    pushMap(producedBy, result, rid)
  }

  const nodeIds = includeOrphans
    ? new Set([...itemsById.keys(), ...referenced])
    : referenced

  const nodes = [...nodeIds].map((id) => ({ id, item: ensureItem(id) }))

  return {
    nodes,
    edges,
    index: { itemsById, recipesById, producedBy, usedIn, forward, backward },
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- buildGraph`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add admin/src/components/craftmap/graph/buildGraph.js admin/src/components/craftmap/graph/buildGraph.test.js
git commit -m "feat(craft-map): pure buildGraph graph derivation with tests"
```

---

## Task 4: `analysis.js` — chain traversal (TDD)

**Files:**
- Create: `admin/src/components/craftmap/graph/analysis.js`
- Test: `admin/src/components/craftmap/graph/analysis.traversal.test.js`

**Interfaces:**
- Consumes: `graph` from `buildGraph` (Task 3).
- Produces: `traverseChain(itemId, graph) -> { upstream: Set<string>, downstream: Set<string>, nodes: Set<string>, edges: Set<string> }`. `upstream`/`downstream` exclude `itemId`; `nodes` includes it; `edges` holds edge ids on the chain.

- [ ] **Step 1: Write the failing test** (`analysis.traversal.test.js`)

```javascript
import { describe, it, expect } from 'vitest'
import { buildGraph } from './buildGraph.js'
import { traverseChain } from './analysis.js'

// 1+2 -> 3 (доска);  3+4 -> 5 (стол)
const items = ['1', '2', '3', '4', '5'].map((id) => ({ id, name: id, emoji: '📦' }))
const recipes = [
  { id: 10, key: 'board', resultItemId: '3', ingredientAId: '1', ingredientBId: '2', successPercent: 100, enabled: true, remains: 0, resultQty: 1 },
  { id: 11, key: 'table', resultItemId: '5', ingredientAId: '3', ingredientBId: '4', successPercent: 100, enabled: true, remains: 0, resultQty: 1 },
]

describe('traverseChain', () => {
  it('collects full upstream (ancestors) of a mid-chain item', () => {
    const g = buildGraph(items, recipes)
    const chain = traverseChain('5', g)
    expect([...chain.upstream].sort()).toEqual(['1', '2', '3', '4'])
    expect([...chain.downstream]).toEqual([])
  })

  it('collects full downstream (descendants) of a base resource', () => {
    const g = buildGraph(items, recipes)
    const chain = traverseChain('1', g)
    expect([...chain.downstream].sort()).toEqual(['3', '5'])
    expect([...chain.upstream]).toEqual([])
  })

  it('includes the selected node and the connecting edges', () => {
    const g = buildGraph(items, recipes)
    const chain = traverseChain('3', g)
    expect(chain.nodes.has('3')).toBe(true)
    // upstream edges producing 3, downstream edges consuming 3
    expect(chain.edges.has('10:a')).toBe(true)
    expect(chain.edges.has('10:b')).toBe(true)
    expect(chain.edges.has('11:a')).toBe(true)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- analysis.traversal`
Expected: FAIL — `traverseChain` is not exported / module missing.

- [ ] **Step 3: Implement `traverseChain` in `analysis.js`**

```javascript
// Pure analysis. NO external imports (must run under root vitest).

export function traverseChain(itemId, graph) {
  const start = String(itemId)
  const { edges, index } = graph
  const edgesByTarget = new Map()
  const edgesBySource = new Map()
  for (const e of edges) {
    if (!edgesByTarget.has(e.target)) edgesByTarget.set(e.target, [])
    if (!edgesBySource.has(e.source)) edgesBySource.set(e.source, [])
    edgesByTarget.get(e.target).push(e)
    edgesBySource.get(e.source).push(e)
  }

  const upstream = new Set()
  const downstream = new Set()
  const chainEdges = new Set()

  // Ancestors: walk backward (edges whose target is the current node).
  const upQueue = [start]
  const upSeen = new Set([start])
  while (upQueue.length) {
    const node = upQueue.shift()
    for (const e of edgesByTarget.get(node) || []) {
      chainEdges.add(e.id)
      if (!upSeen.has(e.source)) {
        upSeen.add(e.source)
        upstream.add(e.source)
        upQueue.push(e.source)
      }
    }
  }

  // Descendants: walk forward (edges whose source is the current node).
  const downQueue = [start]
  const downSeen = new Set([start])
  while (downQueue.length) {
    const node = downQueue.shift()
    for (const e of edgesBySource.get(node) || []) {
      chainEdges.add(e.id)
      if (!downSeen.has(e.target)) {
        downSeen.add(e.target)
        downstream.add(e.target)
        downQueue.push(e.target)
      }
    }
  }

  const nodes = new Set([start, ...upstream, ...downstream])
  return { upstream, downstream, nodes, edges: chainEdges }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- analysis.traversal`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add admin/src/components/craftmap/graph/analysis.js admin/src/components/craftmap/graph/analysis.traversal.test.js
git commit -m "feat(craft-map): chain traversal (upstream/downstream) with tests"
```

---

## Task 5: `analysis.js` — error detection + stats (TDD)

**Files:**
- Modify: `admin/src/components/craftmap/graph/analysis.js` (add two exports)
- Test: `admin/src/components/craftmap/graph/analysis.errors.test.js`

**Interfaces:**
- Consumes: `graph` (Task 3), original `items` + `recipes` arrays.
- Produces:
  - `detectErrors(graph, items) -> Array<{ type, severity, itemIds: string[], edgeIds: string[], message: string }>` where `type ∈ {'cycle','broken-ref','duplicate-recipe','unused-item','unreachable'}`, `severity ∈ {'error','warning','info'}`.
  - `computeStats(graph, items, errors) -> { items, recipes, links, baseResources, finalItems, maxDepth, avgDepth, errors }` (all numbers).

- [ ] **Step 1: Write the failing test** (`analysis.errors.test.js`)

```javascript
import { describe, it, expect } from 'vitest'
import { buildGraph } from './buildGraph.js'
import { detectErrors, computeStats } from './analysis.js'

function typesOf(errors) {
  return [...new Set(errors.map((e) => e.type))].sort()
}

describe('detectErrors', () => {
  it('flags a cycle', () => {
    const items = ['1', '2'].map((id) => ({ id, name: id, emoji: '📦' }))
    // 1+1 -> 2 and 2+2 -> 1  (a cycle 1->2->1)
    const recipes = [
      { id: 1, key: 'a', resultItemId: '2', ingredientAId: '1', ingredientBId: '1', successPercent: 100, enabled: true, remains: 0, resultQty: 1 },
      { id: 2, key: 'b', resultItemId: '1', ingredientAId: '2', ingredientBId: '2', successPercent: 100, enabled: true, remains: 0, resultQty: 1 },
    ]
    const g = buildGraph(items, recipes)
    expect(typesOf(detectErrors(g, items))).toContain('cycle')
  })

  it('flags a broken reference to a missing item', () => {
    const items = [{ id: '3', name: 'Бумага', emoji: '📄' }]
    const recipes = [
      { id: 1, key: 'p', resultItemId: '3', ingredientAId: '1', ingredientBId: '2', successPercent: 100, enabled: true, remains: 0, resultQty: 1 },
    ]
    const g = buildGraph(items, recipes)
    const errors = detectErrors(g, items)
    expect(typesOf(errors)).toContain('broken-ref')
    const broken = errors.find((e) => e.type === 'broken-ref')
    expect(broken.itemIds.sort()).toEqual(['1', '2'])
  })

  it('flags duplicate recipes sharing the same ingredient pair', () => {
    const items = ['1', '2', '3', '4'].map((id) => ({ id, name: id, emoji: '📦' }))
    const recipes = [
      { id: 1, key: 'x', resultItemId: '3', ingredientAId: '1', ingredientBId: '2', successPercent: 100, enabled: true, remains: 0, resultQty: 1 },
      { id: 2, key: 'y', resultItemId: '4', ingredientAId: '2', ingredientBId: '1', successPercent: 100, enabled: true, remains: 0, resultQty: 1 },
    ]
    const g = buildGraph(items, recipes)
    expect(typesOf(detectErrors(g, items))).toContain('duplicate-recipe')
  })

  it('flags items unused by any recipe', () => {
    const items = ['1', '2', '3', '9'].map((id) => ({ id, name: id, emoji: '📦' }))
    const recipes = [
      { id: 1, key: 'x', resultItemId: '3', ingredientAId: '1', ingredientBId: '2', successPercent: 100, enabled: true, remains: 0, resultQty: 1 },
    ]
    const g = buildGraph(items, recipes)
    const unused = detectErrors(g, items).find((e) => e.type === 'unused-item')
    expect(unused.itemIds).toEqual(['9'])
  })
})

describe('computeStats', () => {
  it('computes counts, base/final and depth', () => {
    const items = ['1', '2', '3', '4', '5'].map((id) => ({ id, name: id, emoji: '📦' }))
    const recipes = [
      { id: 10, key: 'board', resultItemId: '3', ingredientAId: '1', ingredientBId: '2', successPercent: 100, enabled: true, remains: 0, resultQty: 1 },
      { id: 11, key: 'table', resultItemId: '5', ingredientAId: '3', ingredientBId: '4', successPercent: 100, enabled: true, remains: 0, resultQty: 1 },
    ]
    const g = buildGraph(items, recipes)
    const stats = computeStats(g, items, [])
    expect(stats.items).toBe(5)
    expect(stats.recipes).toBe(2)
    expect(stats.links).toBe(4)
    expect(stats.baseResources).toBe(3) // 1, 2, 4 (consumed, never produced)
    expect(stats.finalItems).toBe(1)    // 5 (produced, never consumed)
    expect(stats.maxDepth).toBe(2)      // 1->3->5
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- analysis.errors`
Expected: FAIL — `detectErrors`/`computeStats` not exported.

- [ ] **Step 3: Add `detectErrors` and `computeStats` to `analysis.js`**

Append to `analysis.js`:

```javascript
function hasCycle(index, nodeIds) {
  const WHITE = 0
  const GRAY = 1
  const BLACK = 2
  const color = new Map()
  for (const id of nodeIds) color.set(id, WHITE)
  const cycleNodes = new Set()

  const visit = (node) => {
    color.set(node, GRAY)
    for (const next of index.forward.get(node) || []) {
      const c = color.get(next) ?? WHITE
      if (c === GRAY) {
        cycleNodes.add(node)
        cycleNodes.add(next)
        return true
      }
      if (c === WHITE && visit(next)) {
        cycleNodes.add(node)
        return true
      }
    }
    color.set(node, BLACK)
    return false
  }

  let found = false
  for (const id of nodeIds) {
    if ((color.get(id) ?? WHITE) === WHITE && visit(id)) found = true
  }
  return { found, cycleNodes }
}

export function detectErrors(graph, items) {
  const { nodes, edges, index } = graph
  const nodeIds = nodes.map((n) => n.id)
  const errors = []

  // cycles
  const { found, cycleNodes } = hasCycle(index, nodeIds)
  if (found) {
    errors.push({
      type: 'cycle',
      severity: 'error',
      itemIds: [...cycleNodes],
      edgeIds: edges.filter((e) => cycleNodes.has(e.source) && cycleNodes.has(e.target)).map((e) => e.id),
      message: 'Обнаружена циклическая зависимость в рецептах',
    })
  }

  // broken refs (nodes that were only referenced, never defined)
  const missing = nodes.filter((n) => n.item && n.item.missing).map((n) => n.id)
  if (missing.length) {
    errors.push({
      type: 'broken-ref',
      severity: 'error',
      itemIds: missing,
      edgeIds: edges.filter((e) => missing.includes(e.source) || missing.includes(e.target)).map((e) => e.id),
      message: `Рецепты ссылаются на отсутствующие предметы: ${missing.join(', ')}`,
    })
  }

  // duplicate recipes (same unordered ingredient pair among enabled recipes)
  const pairMap = new Map()
  for (const recipe of index.recipesById.values()) {
    if (recipe.enabled === false) continue
    const pair = [String(recipe.ingredientAId), String(recipe.ingredientBId)].sort().join('+')
    if (!pairMap.has(pair)) pairMap.set(pair, [])
    pairMap.get(pair).push(recipe)
  }
  for (const [pair, list] of pairMap) {
    if (list.length > 1) {
      errors.push({
        type: 'duplicate-recipe',
        severity: 'error',
        itemIds: pair.split('+'),
        edgeIds: list.flatMap((r) => [`${r.id}:a`, `${r.id}:b`]),
        message: `Одинаковая пара ингредиентов в рецептах: ${list.map((r) => r.key).join(', ')}`,
      })
    }
  }

  // unused items (real dex items referenced by no recipe)
  const referenced = new Set()
  for (const e of edges) {
    referenced.add(e.source)
    referenced.add(e.target)
  }
  const unused = (items || []).map((i) => String(i.id)).filter((id) => !referenced.has(id))
  if (unused.length) {
    errors.push({
      type: 'unused-item',
      severity: 'info',
      itemIds: unused,
      edgeIds: [],
      message: `Предметы не участвуют ни в одном рецепте: ${unused.length} шт.`,
    })
  }

  // unreachable results (a produced item whose ancestry doesn't bottom out at base resources)
  const memo = new Map()
  const reachable = (id, stack) => {
    if (memo.has(id)) return memo.get(id)
    if (stack.has(id)) return false // cycle
    const producers = index.backward.get(id)
    if (!producers || producers.size === 0) {
      memo.set(id, true) // base resource
      return true
    }
    stack.add(id)
    let ok = true
    for (const ing of producers) {
      const node = graph.nodes.find((n) => n.id === ing)
      if (node && node.item && node.item.missing) { ok = false; break }
      if (!reachable(ing, stack)) { ok = false; break }
    }
    stack.delete(id)
    memo.set(id, ok)
    return ok
  }
  const unreachable = nodeIds.filter((id) => (index.producedBy.get(id) || []).length > 0 && !reachable(id, new Set()))
  if (unreachable.length) {
    errors.push({
      type: 'unreachable',
      severity: 'warning',
      itemIds: unreachable,
      edgeIds: [],
      message: `Недостижимые предметы (нельзя свести к базовым ресурсам): ${unreachable.join(', ')}`,
    })
  }

  return errors
}

export function computeStats(graph, items, errors) {
  const { nodes, edges, index } = graph
  const nodeIds = nodes.map((n) => n.id)

  const baseResources = nodeIds.filter(
    (id) => (index.producedBy.get(id) || []).length === 0 && (index.usedIn.get(id) || []).length > 0,
  )
  const finalItems = nodeIds.filter(
    (id) => (index.usedIn.get(id) || []).length === 0 && (index.producedBy.get(id) || []).length > 0,
  )

  // Longest-path depth on the DAG; cyclic nodes contribute 0 (guarded by stack).
  const depthMemo = new Map()
  const depthOf = (id, stack) => {
    if (depthMemo.has(id)) return depthMemo.get(id)
    if (stack.has(id)) return 0
    const parents = index.backward.get(id)
    if (!parents || parents.size === 0) {
      depthMemo.set(id, 0)
      return 0
    }
    stack.add(id)
    let best = 0
    for (const p of parents) best = Math.max(best, 1 + depthOf(p, stack))
    stack.delete(id)
    depthMemo.set(id, best)
    return best
  }
  const depths = nodeIds.map((id) => depthOf(id, new Set()))
  const nonBase = depths.filter((d) => d > 0)
  const maxDepth = depths.length ? Math.max(...depths) : 0
  const avgDepth = nonBase.length ? nonBase.reduce((a, b) => a + b, 0) / nonBase.length : 0

  return {
    items: (items || []).length,
    recipes: index.recipesById.size,
    links: edges.length,
    baseResources: baseResources.length,
    finalItems: finalItems.length,
    maxDepth,
    avgDepth: Math.round(avgDepth * 10) / 10,
    errors: (errors || []).length,
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- analysis.errors`
Expected: PASS (5 tests).

- [ ] **Step 5: Run the full pure-module suite**

Run: `npm test -- craftmap`
Expected: all buildGraph + analysis tests PASS.

- [ ] **Step 6: Commit**

```bash
git add admin/src/components/craftmap/graph/analysis.js admin/src/components/craftmap/graph/analysis.errors.test.js
git commit -m "feat(craft-map): error detection and stats with tests"
```

---

## Task 6: `layout.js` — dagre auto-layout adapter

**Files:**
- Create: `admin/src/components/craftmap/graph/layout.js`

**Interfaces:**
- Consumes: `nodes` (`[{id}]`) and `edges` (`[{source,target}]`) from the graph model; `@dagrejs/dagre`.
- Produces: `layoutGraph(nodes, edges, opts?) -> { [itemId]: { x: number, y: number } }` (top-left coordinates for React Flow).

- [ ] **Step 1: Implement `layout.js`**

```javascript
import Dagre from '@dagrejs/dagre'

// Assigns positions left-to-right: base resources on the left, final items on the right.
export function layoutGraph(nodes, edges, opts = {}) {
  const { nodeWidth = 230, nodeHeight = 120, rankdir = 'LR', nodesep = 44, ranksep = 130 } = opts
  const g = new Dagre.graphlib.Graph()
  g.setGraph({ rankdir, nodesep, ranksep })
  g.setDefaultEdgeLabel(() => ({}))

  for (const node of nodes) g.setNode(node.id, { width: nodeWidth, height: nodeHeight })
  for (const edge of edges) {
    if (g.hasNode(edge.source) && g.hasNode(edge.target)) g.setEdge(edge.source, edge.target)
  }

  Dagre.layout(g)

  const positions = {}
  for (const node of nodes) {
    const p = g.node(node.id)
    positions[node.id] = { x: p.x - nodeWidth / 2, y: p.y - nodeHeight / 2 }
  }
  return positions
}
```

- [ ] **Step 2: Verify it compiles in the admin build**

Run: `npm --prefix admin run build`
Expected: build succeeds (dagre import resolves).

- [ ] **Step 3: Commit**

```bash
git add admin/src/components/craftmap/graph/layout.js
git commit -m "feat(craft-map): dagre auto-layout adapter"
```

---

## Task 7: `ItemNode.jsx` card component + Craft Map styles

**Files:**
- Create: `admin/src/components/craftmap/nodes/ItemNode.jsx`
- Modify: `admin/src/index.css` (append `craftmap-*` styles)

**Interfaces:**
- Consumes: React Flow node `data` = `{ item, dimmed:boolean, highlighted:boolean, errored:boolean }`.
- Produces: `ItemNode` (default export) — a React Flow custom node type registered as `item` in Task 8. Renders left (target) and right (source) `Handle`s.

- [ ] **Step 1: Implement `ItemNode.jsx`**

```jsx
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
```

- [ ] **Step 2: Append styles to `admin/src/index.css`**

```css
/* ===== Craft Map ===== */
.craftmap-wrap { position: relative; width: 100%; height: 72vh; min-height: 520px;
  border-radius: 18px; overflow: hidden; border: 1px solid var(--panel-border, rgba(255,255,255,.08));
  background: var(--panel-bg, #0e1117); }
.craftmap-flow { width: 100%; height: 100%; }

.craftmap-node { display: flex; align-items: center; gap: 10px; width: 230px;
  padding: 12px 14px; border-radius: 16px; background: rgba(30,34,44,.92);
  border: 1px solid rgba(255,255,255,.10); box-shadow: 0 8px 24px rgba(0,0,0,.35);
  transition: transform .15s ease, box-shadow .15s ease, opacity .2s ease, border-color .2s ease; }
.craftmap-node:hover { transform: translateY(-2px); box-shadow: 0 14px 34px rgba(0,0,0,.45);
  border-color: rgba(120,170,255,.55); }
.craftmap-node-emoji { font-size: 30px; line-height: 1; }
.craftmap-node-body { min-width: 0; flex: 1; }
.craftmap-node-name { font-weight: 600; font-size: 14px; color: #eef1f6;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.craftmap-node-meta { display: flex; gap: 6px; align-items: center; margin-top: 3px; }
.craftmap-node-id { font-size: 11px; color: #8b93a7; }
.craftmap-node-tag { font-size: 11px; color: #b9c2d8; background: rgba(255,255,255,.08);
  border-radius: 999px; padding: 1px 8px; }
.craftmap-node-price { font-size: 11px; color: #d9c07a; margin-top: 3px; }
.craftmap-handle { width: 9px; height: 9px; background: #6f8bff; border: 2px solid #0e1117; }

.craftmap-node-dim { opacity: .18; }
.craftmap-node-hl { border-color: #7ea2ff; box-shadow: 0 0 0 2px rgba(126,162,255,.55), 0 14px 34px rgba(0,0,0,.5); }
.craftmap-node-error { border-color: #ff6b6b; box-shadow: 0 0 0 2px rgba(255,107,107,.5); }
.craftmap-node-missing { border-style: dashed; opacity: .7; }

.craftmap-toolbar { position: absolute; top: 12px; left: 12px; right: 12px; z-index: 6;
  display: flex; gap: 8px; align-items: center; flex-wrap: wrap; pointer-events: none; }
.craftmap-toolbar > * { pointer-events: auto; }
.craftmap-search { flex: 1; min-width: 200px; max-width: 360px; }

.craftmap-props { position: absolute; top: 0; right: 0; height: 100%; width: 320px; z-index: 7;
  background: rgba(16,19,26,.97); border-left: 1px solid rgba(255,255,255,.08);
  box-shadow: -12px 0 30px rgba(0,0,0,.4); overflow-y: auto; padding: 16px; }
.craftmap-errors { position: absolute; bottom: 12px; left: 12px; z-index: 6; max-width: 380px;
  max-height: 40%; overflow-y: auto; background: rgba(16,19,26,.97);
  border: 1px solid rgba(255,255,255,.08); border-radius: 14px; padding: 10px 12px; }
.craftmap-stats { display: flex; gap: 16px; flex-wrap: wrap; padding: 10px 4px; }
.craftmap-stat { display: flex; flex-direction: column; }
.craftmap-stat-value { font-size: 18px; font-weight: 700; color: #eef1f6; }
.craftmap-stat-label { font-size: 11px; color: #8b93a7; }
.craftmap-ctx { position: fixed; z-index: 40; min-width: 220px; background: #151922;
  border: 1px solid rgba(255,255,255,.1); border-radius: 12px; padding: 6px;
  box-shadow: 0 18px 40px rgba(0,0,0,.5); }
.craftmap-ctx button { display: block; width: 100%; text-align: left; background: none; border: 0;
  color: #dfe4ee; padding: 8px 10px; border-radius: 8px; cursor: pointer; font-size: 13px; }
.craftmap-ctx button:hover { background: rgba(255,255,255,.08); }

/* Light theme overrides follow the panel's existing [data-theme="light"] hook. */
[data-theme="light"] .craftmap-wrap { background: #f4f6fb; }
[data-theme="light"] .craftmap-node { background: #ffffff; border-color: rgba(20,30,60,.10);
  box-shadow: 0 8px 22px rgba(30,40,70,.12); }
[data-theme="light"] .craftmap-node-name { color: #1a2230; }
[data-theme="light"] .craftmap-props,
[data-theme="light"] .craftmap-errors,
[data-theme="light"] .craftmap-ctx { background: #ffffff; color: #1a2230; }
```

> Note: If `admin/src/index.css` does not define `--panel-bg`/`--panel-border` or a `[data-theme="light"]` hook, keep the literal fallbacks shown above; they render correctly without the variables.

- [ ] **Step 3: Verify build**

Run: `npm --prefix admin run build`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add admin/src/components/craftmap/nodes/ItemNode.jsx admin/src/index.css
git commit -m "feat(craft-map): item card node component and styles"
```

---

## Task 8: `CraftMapView.jsx` — canvas + data load + drag/save + auto-layout, wired into ContentSection

**Files:**
- Create: `admin/src/components/craftmap/CraftMapView.jsx`
- Modify: `admin/src/pages/sections/ContentSection.jsx` (add `map` tab + import + render)

**Interfaces:**
- Consumes: `fetchCraftMap`, `saveCraftMapPositions` (Task 2); `buildGraph` (Task 3); `layoutGraph` (Task 6); `ItemNode` (Task 7); `traverseChain`, `detectErrors`, `computeStats` (Tasks 4-5).
- Produces: `CraftMapView` (default export) — self-contained tab view. Exposes no props in Phase 1.

This task delivers a working, interactive, self-loading canvas (pan/zoom/minimap/controls, drag-persist, auto-layout button, empty/error states). Search/filters/chain-highlight/panels/context-menu/stats/errors panels are layered on in Tasks 9-13; this task renders `computeStats`/`detectErrors` results only implicitly (wired later). To keep the deliverable testable now, it renders the graph, a minimal toolbar with the auto-layout button, and persists positions.

- [ ] **Step 1: Implement `CraftMapView.jsx`**

```jsx
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
```

- [ ] **Step 2: Wire the tab into `ContentSection.jsx`**

Add the import near the other component imports (after line 4 `import CraftRecipeWizard ...`):
```jsx
import CraftMapView from '../../components/craftmap/CraftMapView'
```

Add the tab to the `TABS` array (after the `craft` entry, ~line 54):
```jsx
  { id: 'map', label: '🗺 Карта' },
```

Render it after the `tab === 'craft'` block (find the closing of that block near line 1090, before `{tab === 'quests' && (`):
```jsx
      {tab === 'map' && <CraftMapView />}
```

- [ ] **Step 3: Manual verification (run the admin app)**

Run: `npm --prefix admin run dev` (and the backend so the API responds).
Verify:
- The «🗺 Карта» tab appears and opens without console errors.
- Cards render with emoji/name/#id; edges connect ingredients → results.
- Wheel zoom, drag-to-pan, minimap, and Controls work.
- Drag a card, reload the page → the card keeps its position (persisted to DB).
- «Авто-раскладка» rearranges cards left→right.
- Stop the backend and reload → error state with a working «Повторить».

- [ ] **Step 4: Commit**

```bash
git add admin/src/components/craftmap/CraftMapView.jsx admin/src/pages/sections/ContentSection.jsx
git commit -m "feat(craft-map): react-flow canvas with drag-persist and auto-layout, wired into content tab"
```

---

## Task 9: Search + filters (dim/highlight) via `useCraftMapState`

**Files:**
- Create: `admin/src/components/craftmap/useCraftMapState.js`
- Create: `admin/src/components/craftmap/panels/SearchBar.jsx`
- Create: `admin/src/components/craftmap/panels/FilterPanel.jsx`
- Modify: `admin/src/components/craftmap/CraftMapView.jsx` (consume the hook; apply node/edge visual state)

**Interfaces:**
- Produces: `useCraftMapState(graph) -> { query, setQuery, categories, hiddenCategories, toggleCategory, matchedIds: Set<string>, visibleIds: Set<string> }`.
  - `matchedIds`: node ids matching `query` across name/id/sorting/bio (empty query → empty set = "no active search").
  - `visibleIds`: node ids not hidden by category filter.
  - `categories`: sorted unique `sorting` values present.
- Produces: `SearchBar({ query, onChange, count })`, `FilterPanel({ categories, hidden, onToggle })`.

- [ ] **Step 1: Implement `useCraftMapState.js`**

```javascript
import { useMemo, useState } from 'react'

export function useCraftMapState(graph) {
  const [query, setQuery] = useState('')
  const [hiddenCategories, setHidden] = useState(() => new Set())

  const categories = useMemo(() => {
    const set = new Set()
    for (const n of graph.nodes) if (n.item.sorting) set.add(n.item.sorting)
    return [...set].sort()
  }, [graph])

  const matchedIds = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return new Set()
    const out = new Set()
    for (const n of graph.nodes) {
      const i = n.item
      const hay = [i.id, i.name, i.name1, i.sorting, i.bio].filter(Boolean).join(' ').toLowerCase()
      if (hay.includes(q)) out.add(n.id)
    }
    return out
  }, [graph, query])

  const visibleIds = useMemo(() => {
    const out = new Set()
    for (const n of graph.nodes) {
      if (n.item.sorting && hiddenCategories.has(n.item.sorting)) continue
      out.add(n.id)
    }
    return out
  }, [graph, hiddenCategories])

  const toggleCategory = (cat) => {
    setHidden((prev) => {
      const next = new Set(prev)
      if (next.has(cat)) next.delete(cat)
      else next.add(cat)
      return next
    })
  }

  return { query, setQuery, categories, hiddenCategories, toggleCategory, matchedIds, visibleIds }
}
```

- [ ] **Step 2: Implement `SearchBar.jsx` and `FilterPanel.jsx`**

`SearchBar.jsx`:
```jsx
export default function SearchBar({ query, onChange, count }) {
  return (
    <div className="craftmap-search">
      <input
        className="panel-users-input"
        placeholder="Поиск: название, ID, категория, описание…"
        value={query}
        onChange={(e) => onChange(e.target.value)}
      />
      {query ? <span className="panel-shelf-muted">Найдено: {count}</span> : null}
    </div>
  )
}
```

`FilterPanel.jsx`:
```jsx
export default function FilterPanel({ categories, hidden, onToggle }) {
  if (!categories.length) return null
  return (
    <div className="craftmap-filters" style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
      {categories.map((cat) => (
        <button
          key={cat}
          type="button"
          className={`craftmap-node-tag${hidden.has(cat) ? '' : ' craftmap-tag-active'}`}
          style={{ cursor: 'pointer', opacity: hidden.has(cat) ? 0.4 : 1 }}
          onClick={() => onToggle(cat)}
        >
          {cat}
        </button>
      ))}
    </div>
  )
}
```

- [ ] **Step 3: Consume in `CraftMapView.jsx`**

Add imports:
```jsx
import { useCraftMapState } from './useCraftMapState'
import SearchBar from './panels/SearchBar'
import FilterPanel from './panels/FilterPanel'
```

After `const graph = useMemo(...)`, add:
```jsx
  const mapState = useCraftMapState(graph)
```

Add an effect that recomputes node visual state from search/filter (place after the `graph` memo and `mapState`):
```jsx
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
```

Add the search + filters to the toolbar (inside `.craftmap-toolbar`, before the count span):
```jsx
        <SearchBar query={mapState.query} onChange={mapState.setQuery} count={mapState.matchedIds.size} />
        <FilterPanel categories={mapState.categories} hidden={mapState.hiddenCategories} onToggle={mapState.toggleCategory} />
```

- [ ] **Step 4: Manual verification**

Run: `npm --prefix admin run dev`
Verify: typing in search dims non-matches and highlights matches; toggling a category chip hides/shows those cards; clearing search restores all.

- [ ] **Step 5: Commit**

```bash
git add admin/src/components/craftmap/useCraftMapState.js admin/src/components/craftmap/panels/SearchBar.jsx admin/src/components/craftmap/panels/FilterPanel.jsx admin/src/components/craftmap/CraftMapView.jsx
git commit -m "feat(craft-map): search dim/highlight and category filters"
```

---

## Task 10: Chain highlight on selection

**Files:**
- Modify: `admin/src/components/craftmap/CraftMapView.jsx`

**Interfaces:**
- Consumes: `traverseChain(itemId, graph)` (Task 4).
- Produces: selection state `selectedId` + a "focus chain" mode dimming everything outside the selected item's chain; clears on background click.

- [ ] **Step 1: Add selection + chain highlighting to `CraftMapView.jsx`**

Add import:
```jsx
import { traverseChain } from './graph/analysis'
```

Add state after `mapState`:
```jsx
  const [selectedId, setSelectedId] = useState(null)
```

Add the chain memo + a visual-apply effect (after the search effect):
```jsx
  const chain = useMemo(
    () => (selectedId ? traverseChain(selectedId, graph) : null),
    [selectedId, graph],
  )

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
```

Add handlers and wire them to `ReactFlow`:
```jsx
  const onNodeClick = useCallback((_evt, node) => { setSelectedId(node.id) }, [])
  const onPaneClick = useCallback(() => {
    setSelectedId(null)
    setEdges((prev) => prev.map((e) => ({ ...e, animated: false, style: { ...(e.style || {}), opacity: 1 } })))
    setNodes((prev) => prev.map((n) => ({ ...n, data: { ...n.data, dimmed: false, highlighted: false } })))
  }, [setNodes, setEdges])
```

On the `<ReactFlow>` element add:
```jsx
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
```

> Note: When `selectedId` is set, chain highlighting takes precedence over search dimming (the search effect still runs on query change; clicking a node re-applies chain state). This is acceptable for Phase 1 — the two modes are used one at a time.

- [ ] **Step 2: Manual verification**

Run: `npm --prefix admin run dev`
Verify: clicking a card dims everything except its full upstream+downstream chain and animates the chain edges; clicking empty canvas clears it.

- [ ] **Step 3: Commit**

```bash
git add admin/src/components/craftmap/CraftMapView.jsx
git commit -m "feat(craft-map): full-chain highlight on node selection"
```

---

## Task 11: `PropertiesPanel.jsx` — right-side item details

**Files:**
- Create: `admin/src/components/craftmap/panels/PropertiesPanel.jsx`
- Modify: `admin/src/components/craftmap/CraftMapView.jsx` (render when a node is selected)

**Interfaces:**
- Consumes: selected `item`, `graph` (for `producedBy`/`usedIn`), and an `onClose`, `onGoTo(itemId)` callbacks.
- Produces: `PropertiesPanel({ item, graph, onClose, onGoTo })`.

- [ ] **Step 1: Implement `PropertiesPanel.jsx`**

```jsx
export default function PropertiesPanel({ item, graph, onClose, onGoTo }) {
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
        <div key={r.id} className="panel-shelf-muted">{recipeLine(r)}</div>
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
```

- [ ] **Step 2: Render in `CraftMapView.jsx`**

Add import:
```jsx
import PropertiesPanel from './panels/PropertiesPanel'
```

Compute selected item:
```jsx
  const selectedItem = useMemo(
    () => (selectedId ? (graph.index.itemsById.get(selectedId) || graph.nodes.find((n) => n.id === selectedId)?.item) : null),
    [selectedId, graph],
  )
```

Add a `goTo` helper that selects and centers the viewport on the node (implements "быстрый переход / авто-центрирование"):
```jsx
  const goTo = useCallback((itemId) => {
    const id = String(itemId)
    setSelectedId(id)
    const node = nodes.find((n) => n.id === id)
    if (node && rfRef.current) {
      // node is ~230x120; offset to its center
      rfRef.current.setCenter(node.position.x + 115, node.position.y + 60, { zoom: 1.2, duration: 400 })
    }
  }, [nodes])
```

Render the panel inside `.craftmap-wrap` (after `</ReactFlow>`):
```jsx
      {selectedItem ? (
        <PropertiesPanel item={selectedItem} graph={graph} onClose={onPaneClick} onGoTo={goTo} />
      ) : null}
```

- [ ] **Step 3: Manual verification**

Run: `npm --prefix admin run dev`
Verify: clicking a card opens the right panel with its details, "рецепты создания", and clickable "используется в" entries that jump to the target item; ✕ closes it.

- [ ] **Step 4: Commit**

```bash
git add admin/src/components/craftmap/panels/PropertiesPanel.jsx admin/src/components/craftmap/CraftMapView.jsx
git commit -m "feat(craft-map): properties side panel with recipes and usage"
```

---

## Task 12: `ContextMenu.jsx` — right-click actions

**Files:**
- Create: `admin/src/components/craftmap/panels/ContextMenu.jsx`
- Modify: `admin/src/components/craftmap/CraftMapView.jsx`

**Interfaces:**
- Produces: `ContextMenu({ x, y, actions, onClose })` where `actions = [{ label, onClick }]`.
- Read-only actions: показать цепочку, выделить связанные, копировать ID, копировать ссылку, центрировать.

- [ ] **Step 1: Implement `ContextMenu.jsx`**

```jsx
import { useEffect } from 'react'

export default function ContextMenu({ x, y, actions, onClose }) {
  useEffect(() => {
    const close = () => onClose()
    window.addEventListener('click', close)
    window.addEventListener('scroll', close, true)
    return () => {
      window.removeEventListener('click', close)
      window.removeEventListener('scroll', close, true)
    }
  }, [onClose])

  return (
    <div className="craftmap-ctx" style={{ left: x, top: y }} onClick={(e) => e.stopPropagation()}>
      {actions.map((a) => (
        <button key={a.label} type="button" onClick={() => { a.onClick(); onClose() }}>{a.label}</button>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Wire into `CraftMapView.jsx`**

Add import:
```jsx
import ContextMenu from './panels/ContextMenu'
```

Add state:
```jsx
  const [ctxMenu, setCtxMenu] = useState(null)
```

Add the node context-menu handler:
```jsx
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
```

On `<ReactFlow>` add:
```jsx
        onNodeContextMenu={onNodeContextMenu}
```

Render the menu inside `.craftmap-wrap`:
```jsx
      {ctxMenu ? <ContextMenu x={ctxMenu.x} y={ctxMenu.y} actions={ctxMenu.actions} onClose={() => setCtxMenu(null)} /> : null}
```

- [ ] **Step 3: Manual verification**

Run: `npm --prefix admin run dev`
Verify: right-clicking a card opens the menu at the cursor; "Показать цепочку" highlights the chain; "Копировать ID" copies; clicking elsewhere closes the menu.

- [ ] **Step 4: Commit**

```bash
git add admin/src/components/craftmap/panels/ContextMenu.jsx admin/src/components/craftmap/CraftMapView.jsx
git commit -m "feat(craft-map): node context menu with read-only actions"
```

---

## Task 13: `StatsBar.jsx` + `ErrorsPanel.jsx`

**Files:**
- Create: `admin/src/components/craftmap/panels/StatsBar.jsx`
- Create: `admin/src/components/craftmap/panels/ErrorsPanel.jsx`
- Modify: `admin/src/components/craftmap/CraftMapView.jsx`

**Interfaces:**
- Consumes: `computeStats`, `detectErrors` (Task 5).
- Produces: `StatsBar({ stats })`, `ErrorsPanel({ errors, onFocus })` where `onFocus(itemIds)` highlights offending nodes.

- [ ] **Step 1: Implement `StatsBar.jsx`**

```jsx
const FIELDS = [
  ['items', 'Предметов'],
  ['recipes', 'Рецептов'],
  ['links', 'Связей'],
  ['baseResources', 'Базовых'],
  ['finalItems', 'Конечных'],
  ['maxDepth', 'Макс. глубина'],
  ['avgDepth', 'Сред. глубина'],
  ['errors', 'Ошибок'],
]

export default function StatsBar({ stats }) {
  if (!stats) return null
  return (
    <div className="craftmap-stats">
      {FIELDS.map(([key, label]) => (
        <div className="craftmap-stat" key={key}>
          <span className="craftmap-stat-value" style={key === 'errors' && stats.errors > 0 ? { color: '#ff6b6b' } : undefined}>
            {stats[key]}
          </span>
          <span className="craftmap-stat-label">{label}</span>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Implement `ErrorsPanel.jsx`**

```jsx
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
```

- [ ] **Step 3: Wire into `CraftMapView.jsx`**

Add imports:
```jsx
import { detectErrors, computeStats } from './graph/analysis'
import StatsBar from './panels/StatsBar'
import ErrorsPanel from './panels/ErrorsPanel'
```

Add memos:
```jsx
  const errors = useMemo(() => detectErrors(graph, raw.items), [graph, raw.items])
  const stats = useMemo(() => computeStats(graph, raw.items, errors), [graph, raw.items, errors])
```

Add a focus handler that marks nodes errored + centers:
```jsx
  const focusItems = useCallback((itemIds) => {
    const set = new Set(itemIds.map(String))
    setNodes((prev) => prev.map((n) => ({
      ...n,
      data: { ...n.data, errored: set.has(n.id), dimmed: set.size > 0 && !set.has(n.id) },
    })))
  }, [setNodes])
```

Render `StatsBar` above the canvas wrap (in the returned JSX, wrap the existing `.craftmap-wrap` so stats sit on top):
```jsx
  // return (<> <StatsBar stats={stats} /> <div className="craftmap-wrap"> … </div> </>)
```
Concretely, change the top-level `return (` to a fragment:
```jsx
  return (
    <>
      <StatsBar stats={stats} />
      <div className="craftmap-wrap">
        {/* existing toolbar + ReactFlow + panels */}
        <ErrorsPanel errors={errors} onFocus={focusItems} />
      </div>
    </>
  )
```
Place `<ErrorsPanel … />` inside `.craftmap-wrap` (bottom-left, per CSS). Keep the existing error-state early-return unchanged.

- [ ] **Step 4: Manual verification**

Run: `npm --prefix admin run dev`
Verify: the stats row shows counts/depth/error count above the canvas; the errors panel lists detected problems; clicking an error highlights the offending cards (red) and dims the rest.

- [ ] **Step 5: Commit**

```bash
git add admin/src/components/craftmap/panels/StatsBar.jsx admin/src/components/craftmap/panels/ErrorsPanel.jsx admin/src/components/craftmap/CraftMapView.jsx
git commit -m "feat(craft-map): stats bar and error panel with focus-on-map"
```

---

## Task 14: Final integration pass — full build, test suite, QA checklist

**Files:**
- Modify (only if issues found): any `craftmap/*` file.

- [ ] **Step 1: Run the full pure-module test suite**

Run: `npm test -- craftmap`
Expected: all `buildGraph` + `analysis` tests PASS.

- [ ] **Step 2: Run the backend helper test**

Run: `python tests/test_craft_map_positions.py`
Expected: `ok`

- [ ] **Step 3: Production build of the admin app**

Run: `npm --prefix admin run build`
Expected: build succeeds with no errors.

- [ ] **Step 4: Manual QA checklist (admin dev + backend running)**

Verify each, fixing any regressions inline:
- [ ] «🗺 Карта» tab opens; cards + edges render; no console errors.
- [ ] Pan (drag canvas), wheel zoom, minimap navigation, Controls all work.
- [ ] Auto-layout button arranges base→final left-to-right.
- [ ] Drag a card → reload → position persists (DB round-trip).
- [ ] Search dims non-matches / highlights matches; clearing restores.
- [ ] Category chips hide/show their cards.
- [ ] Click a card → full chain highlighted, rest dimmed, chain edges animated; pane click clears.
- [ ] Right panel shows item details, "рецепты создания", clickable "используется в".
- [ ] Right-click → context menu; "Копировать ID" works; menu closes on outside click.
- [ ] Stats row shows correct counts; error panel lists problems; clicking an error focuses the offending cards.
- [ ] Toggle admin theme (light/dark) → both render correctly.
- [ ] Stop backend, reload → error state with working «Повторить».
- [ ] Existing «Крафт» tab and `CraftRecipeWizard` still work unchanged.

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "chore(craft-map): final integration fixes and QA pass"
```

---

## Notes for the executor

- Only `layout.js` imports `@dagrejs/dagre`; keep `buildGraph.js` and `analysis.js` free of npm imports so `npm test` (root vitest) discovers and runs their colocated `*.test.js` files.
- Deliberate deviation from the spec's testing list: `layout.js` is **not** unit-tested. It imports `@dagrejs/dagre`, which lives in `admin/node_modules` and is not resolvable by the repo-root vitest; it is a thin adapter over a well-tested library. It is verified by the admin build (Task 6) and the auto-layout QA check (Task 14) instead. The graph logic worth testing (derivation, traversal, errors, stats) lives in the dep-free modules that *are* unit-tested.
- The map is read-only for recipes in Phase 1. Do not add create/edit/delete affordances — those belong to a later phase that also expands the DB model (N ingredients + per-edge quantities).
- If `ensure_content_registry_loaded` or `all_craft_recipes` import paths differ at implementation time, mirror exactly what `get_content_overview` in `server/admin_content.py` already does (it imports them locally inside the function).
- React Flow v12 requires importing its stylesheet once (`import '@xyflow/react/dist/style.css'`), done in `CraftMapView.jsx`.
