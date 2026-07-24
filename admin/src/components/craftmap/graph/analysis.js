// Pure analysis. NO external imports (must run under root vitest).

export function traverseChain(itemId, graph) {
  const start = String(itemId)
  const { edges } = graph
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

function hasCycle(index, nodeIds) {
  const WHITE = 0
  const GRAY = 1
  const BLACK = 2
  const color = new Map()
  for (const id of nodeIds) color.set(id, WHITE)
  const cycleNodes = new Set()
  const path = []

  const visit = (node) => {
    color.set(node, GRAY)
    path.push(node)
    for (const next of index.forward.get(node) || []) {
      const c = color.get(next) ?? WHITE
      if (c === GRAY) {
        // back-edge: cycle members are the path segment from `next` to the top
        const start = path.indexOf(next)
        if (start !== -1) {
          for (let i = start; i < path.length; i++) cycleNodes.add(path[i])
        }
      } else if (c === WHITE) {
        visit(next)
      }
    }
    path.pop()
    color.set(node, BLACK)
  }

  for (const id of nodeIds) {
    if ((color.get(id) ?? WHITE) === WHITE) visit(id)
  }
  return { found: cycleNodes.size > 0, cycleNodes }
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

  // unreachable results: a produced item is reachable if it has no producers
  // (base resource) OR at least one recipe whose ingredients are all reachable
  // and non-missing. Only positive results are memoized (a false may be a
  // transient stack sentinel).
  const nodeById = new Map(nodes.map((n) => [n.id, n]))
  const reachMemo = new Map()
  const isReachable = (id, stack) => {
    if (reachMemo.has(id)) return reachMemo.get(id)
    if (stack.has(id)) return false // cycle along this path
    const recipeIds = index.producedBy.get(id) || []
    if (recipeIds.length === 0) {
      reachMemo.set(id, true) // base resource
      return true
    }
    stack.add(id)
    let ok = false
    for (const rid of recipeIds) {
      const recipe = index.recipesById.get(rid)
      if (!recipe) continue
      const ings = [String(recipe.ingredientAId), String(recipe.ingredientBId)]
      let allOk = true
      for (const ing of ings) {
        const node = nodeById.get(ing)
        if (node && node.item && node.item.missing) { allOk = false; break }
        if (!isReachable(ing, stack)) { allOk = false; break }
      }
      if (allOk) { ok = true; break } // at least one recipe resolves
    }
    stack.delete(id)
    if (ok) reachMemo.set(id, true)
    return ok
  }
  const unreachable = nodeIds.filter(
    (id) => (index.producedBy.get(id) || []).length > 0 && !isReachable(id, new Set()),
  )
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

  // Longest-path depth on the DAG. Cyclic nodes have undefined depth (null),
  // are not memoized while transient, and are excluded from the stats.
  const depthMemo = new Map()
  const depthOf = (id, stack) => {
    if (depthMemo.has(id)) return depthMemo.get(id)
    if (stack.has(id)) return null // cyclic: depth undefined
    const parents = index.backward.get(id)
    if (!parents || parents.size === 0) {
      depthMemo.set(id, 0)
      return 0
    }
    stack.add(id)
    let best = 0
    let cyclic = false
    for (const p of parents) {
      const d = depthOf(p, stack)
      if (d === null) { cyclic = true; break }
      best = Math.max(best, 1 + d)
    }
    stack.delete(id)
    if (cyclic) return null // do not memoize a transient cyclic result
    depthMemo.set(id, best)
    return best
  }
  const depths = nodeIds.map((id) => depthOf(id, new Set())).filter((d) => d !== null)
  const nonBase = depths.filter((d) => d > 0)
  const maxDepth = depths.length ? Math.max(...depths) : 0
  const avgDepth = nonBase.length ? nonBase.reduce((a, b) => a + b, 0) / nonBase.length : 0

  return {
    items: (items || []).length,
    recipes: index.recipesById.size,
    // Ingredient->recipe contributions (a/b slots), not raw render edges —
    // the recipe node's synthetic `out` hop is a rendering detail, not a link.
    links: edges.filter((e) => e.slot !== 'out').length,
    baseResources: baseResources.length,
    finalItems: finalItems.length,
    maxDepth,
    avgDepth: Math.round(avgDepth * 10) / 10,
    errors: (errors || []).length,
  }
}
