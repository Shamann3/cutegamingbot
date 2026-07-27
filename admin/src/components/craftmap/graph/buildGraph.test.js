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
