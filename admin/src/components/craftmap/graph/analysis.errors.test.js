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
