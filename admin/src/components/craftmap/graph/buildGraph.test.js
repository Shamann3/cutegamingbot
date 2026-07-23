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

  it('does not duplicate a recipe id in usedIn when both ingredient slots are the same item', () => {
    const sameItems = [
      { id: '1', name: 'Бревно', emoji: '🪵' },
      { id: '2', name: 'Доска', emoji: '🪵' },
    ]
    const sameRecipes = [
      { id: 20, key: 'plank', resultItemId: '2', ingredientAId: '1', ingredientBId: '1', successPercent: 100, enabled: true, remains: 0, resultQty: 1 },
    ]
    const g = buildGraph(sameItems, sameRecipes)
    expect(g.index.usedIn.get('1')).toEqual([20]) // not [20, 20]
    expect(g.edges.map((e) => e.id).sort()).toEqual(['20:a', '20:b']) // both slot edges still present
  })
})
