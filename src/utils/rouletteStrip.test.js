import { describe, expect, it } from 'vitest'
import { buildStrip, landingOffset } from './rouletteStrip'

const pool = [
  { emoji: '🌾', rarity: 'common' },
  { emoji: '🖼️', rarity: 'rare' },
  { emoji: '🐉', rarity: 'legendary' },
]
const result = { emoji: '👑', rarity: 'legendary' }

describe('rouletteStrip', () => {
  it('places the result at resultIndex and fills the rest from the pool', () => {
    const { cells, resultIndex } = buildStrip(result, pool, { length: 20, resultIndex: 15 })
    expect(cells).toHaveLength(20)
    expect(resultIndex).toBe(15)
    expect(cells[15].emoji).toBe('👑')
    expect(cells[15].rarity).toBe('legendary')
    // non-result cells come from the pool
    expect(pool.map((p) => p.emoji)).toContain(cells[0].emoji)
  })
  it('gives every cell a unique key', () => {
    const { cells } = buildStrip(result, pool, { length: 30 })
    const keys = new Set(cells.map((c) => c.key))
    expect(keys.size).toBe(30)
  })
  it('defaults resultIndex near the end when not given', () => {
    const { resultIndex, cells } = buildStrip(result, pool, { length: 40 })
    expect(resultIndex).toBe(35)
    expect(cells[35].emoji).toBe('👑')
  })
  it('computes a landing offset that centers the result cell', () => {
    // cell 15, width 78, gap 10, viewport 300
    // -(15*88 + 39 - 150) = -(1320 + 39 - 150) = -1209
    expect(landingOffset(15, 78, 10, 300)).toBe(-1209)
  })
  it('handles empty pool by filling with the result', () => {
    const { cells } = buildStrip(result, [], { length: 5, resultIndex: 3 })
    expect(cells).toHaveLength(5)
    expect(cells[3].emoji).toBe('👑')
  })
})
