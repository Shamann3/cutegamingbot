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
