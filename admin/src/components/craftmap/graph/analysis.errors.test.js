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

describe('detectErrors — correctness regressions', () => {
  it('cycle error lists only true cycle members, not feeder ancestors', () => {
    // 5 feeds into a 1<->2 cycle; 5 is NOT part of the cycle
    const items = ['1', '2', '5'].map((id) => ({ id, name: id, emoji: '📦' }))
    const recipes = [
      { id: 1, key: 'a', resultItemId: '2', ingredientAId: '1', ingredientBId: '1', successPercent: 100, enabled: true, remains: 0, resultQty: 1 },
      { id: 2, key: 'b', resultItemId: '1', ingredientAId: '2', ingredientBId: '2', successPercent: 100, enabled: true, remains: 0, resultQty: 1 },
      { id: 3, key: 'c', resultItemId: '1', ingredientAId: '5', ingredientBId: '5', successPercent: 100, enabled: true, remains: 0, resultQty: 1 },
    ]
    const g = buildGraph(items, recipes)
    const cycle = detectErrors(g, items).find((e) => e.type === 'cycle')
    expect(cycle).toBeDefined()
    expect([...cycle.itemIds].sort()).toEqual(['1', '2'])
    expect(cycle.itemIds).not.toContain('5')
  })

  it('does NOT flag an item as unreachable when at least one recipe is valid', () => {
    // 3 can be made by R1 (1+2 -> 3, both base) OR R2 (9+9 -> 3, 9 is missing)
    const items = ['1', '2', '3'].map((id) => ({ id, name: id, emoji: '📦' }))
    const recipes = [
      { id: 1, key: 'r1', resultItemId: '3', ingredientAId: '1', ingredientBId: '2', successPercent: 100, enabled: true, remains: 0, resultQty: 1 },
      { id: 2, key: 'r2', resultItemId: '3', ingredientAId: '9', ingredientBId: '9', successPercent: 100, enabled: true, remains: 0, resultQty: 1 },
    ]
    const g = buildGraph(items, recipes)
    const unreachable = detectErrors(g, items).find((e) => e.type === 'unreachable')
    expect(unreachable).toBeUndefined()
  })
})

describe('computeStats — depth with cycles', () => {
  it('reports zero depth for a pure cycle and does not corrupt maxDepth/avgDepth', () => {
    const items = ['1', '2'].map((id) => ({ id, name: id, emoji: '📦' }))
    const recipes = [
      { id: 1, key: 'a', resultItemId: '2', ingredientAId: '1', ingredientBId: '1', successPercent: 100, enabled: true, remains: 0, resultQty: 1 },
      { id: 2, key: 'b', resultItemId: '1', ingredientAId: '2', ingredientBId: '2', successPercent: 100, enabled: true, remains: 0, resultQty: 1 },
    ]
    const g = buildGraph(items, recipes)
    const stats = computeStats(g, items, [])
    expect(stats.maxDepth).toBe(0)
    expect(stats.avgDepth).toBe(0)
  })

  it('reports avgDepth for the linear DAG fixture', () => {
    const items = ['1', '2', '3', '4', '5'].map((id) => ({ id, name: id, emoji: '📦' }))
    const recipes = [
      { id: 10, key: 'board', resultItemId: '3', ingredientAId: '1', ingredientBId: '2', successPercent: 100, enabled: true, remains: 0, resultQty: 1 },
      { id: 11, key: 'table', resultItemId: '5', ingredientAId: '3', ingredientBId: '4', successPercent: 100, enabled: true, remains: 0, resultQty: 1 },
    ]
    const g = buildGraph(items, recipes)
    const stats = computeStats(g, items, [])
    // depths: 3 -> 1, 5 -> 2; avg over non-base = (1 + 2) / 2 = 1.5
    expect(stats.avgDepth).toBe(1.5)
  })
})
