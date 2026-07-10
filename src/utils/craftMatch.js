export function ingredientPairKey(ids) {
  return [...ids].map(String).sort().join('|')
}

function ingredientTotals(ingredients) {
  const totals = new Map()
  for (const item of ingredients) {
    totals.set(item.id, (totals.get(item.id) ?? 0) + item.qty)
  }
  return totals
}

function hasIngredients(ingredients) {
  const ownedById = new Map(ingredients.map((item) => [item.id, item.owned]))
  for (const [id, qty] of ingredientTotals(ingredients)) {
    if ((ownedById.get(id) ?? 0) < qty) return false
  }
  return true
}

export function findMatchingRecipe(recipes, slotA, slotB) {
  if (!slotA || !slotB) return null

  const pairKey = ingredientPairKey([slotA, slotB])
  return recipes.find((recipe) => {
    if (recipe.ingredients.length !== 2) return false
    const recipeKey = ingredientPairKey(recipe.ingredients.map((item) => item.id))
    if (recipeKey !== pairKey) return false
    return hasIngredients(recipe.ingredients)
  }) ?? null
}

export function buildCraftInventory(recipes) {
  const map = new Map()

  for (const recipe of recipes) {
    for (const ingredient of recipe.ingredients) {
      if (ingredient.owned <= 0) continue
      const existing = map.get(ingredient.id)
      if (!existing || ingredient.owned > existing.owned) {
        map.set(ingredient.id, {
          id: ingredient.id,
          name: ingredient.name,
          emoji: ingredient.emoji,
          owned: ingredient.owned,
        })
      }
    }
  }

  return [...map.values()].sort((left, right) => left.name.localeCompare(right.name, 'ru'))
}

export function formatRecipeLine(recipe) {
  const [first, second] = recipe.ingredients
  const qty = recipe.result?.qty > 1 ? ` ×${recipe.result.qty}` : ''
  return `${first.name} + ${second.name} → ${recipe.result.emoji} ${recipe.result.name}${qty}`
}
