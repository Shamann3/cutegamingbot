import { describe, it, expect } from 'vitest'
import { nodeVisual, edgeVisual } from './viewState.js'

const allVisible = new Set(['1', '2', '3'])
const base = { selectedId: null, chainNodes: null, chainEdges: null, matchedIds: new Set(), visibleIds: allVisible, errorFocus: null }

describe('nodeVisual', () => {
  it('is neutral with no selection/search/errors', () => {
    expect(nodeVisual('1', base)).toEqual({ hidden: false, dimmed: false, highlighted: false, errored: false })
  })
  it('hides + dims a node filtered out by category', () => {
    const v = nodeVisual('9', { ...base, visibleIds: allVisible })
    expect(v.hidden).toBe(true)
    expect(v.dimmed).toBe(true)
  })
  it('search: highlights matches, dims the rest', () => {
    const ctx = { ...base, matchedIds: new Set(['1']) }
    expect(nodeVisual('1', ctx)).toMatchObject({ highlighted: true, dimmed: false })
    expect(nodeVisual('2', ctx)).toMatchObject({ highlighted: false, dimmed: true })
  })
  it('chain takes precedence over search', () => {
    const ctx = { ...base, selectedId: '1', chainNodes: new Set(['1', '2']), matchedIds: new Set(['3']) }
    expect(nodeVisual('1', ctx)).toMatchObject({ highlighted: true, dimmed: false })
    expect(nodeVisual('2', ctx)).toMatchObject({ dimmed: false })
    expect(nodeVisual('3', ctx)).toMatchObject({ dimmed: true, highlighted: false })
  })
  it('errorFocus takes precedence over chain and search', () => {
    const ctx = { ...base, selectedId: '1', chainNodes: new Set(['1', '2']), errorFocus: new Set(['3']) }
    expect(nodeVisual('3', ctx)).toMatchObject({ errored: true, dimmed: false })
    expect(nodeVisual('1', ctx)).toMatchObject({ errored: false, dimmed: true })
  })
})

describe('edgeVisual', () => {
  it('dashes disabled edges, full opacity when no chain', () => {
    expect(edgeVisual('10:a', false, base)).toMatchObject({ dashed: true, opacity: 0.6, animated: false })
  })
  it('animates chain edges and dims the rest when a chain is active', () => {
    const ctx = { ...base, selectedId: '1', chainEdges: new Set(['10:a']) }
    expect(edgeVisual('10:a', true, ctx)).toMatchObject({ animated: true, opacity: 1 })
    expect(edgeVisual('11:a', true, ctx)).toMatchObject({ animated: false, opacity: 0.12 })
  })
})
