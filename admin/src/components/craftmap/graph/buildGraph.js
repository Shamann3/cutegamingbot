// Pure graph derivation. NO external imports (must run under root vitest).

function pushMap(map, key, value) {
  const arr = map.get(key)
  if (arr) arr.push(value)
  else map.set(key, [value])
}

function pushMapUnique(map, key, value) {
  const arr = map.get(key)
  if (arr) {
    if (!arr.includes(value)) arr.push(value)
  } else {
    map.set(key, [value])
  }
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
