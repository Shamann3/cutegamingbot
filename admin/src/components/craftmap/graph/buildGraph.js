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
