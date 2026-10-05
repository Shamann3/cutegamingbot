import { describe, expect, it } from 'vitest'
import { ladderRanks, positionOrder, ranksDiffer } from './rankLadder'

describe('rank ladder', () => {
  it('puts the top post on rank 4, never on rank 1 by default', () => {
    expect(ladderRanks([10])).toEqual([{ id: 10, rank: 4, ladder: 0 }])
    expect(ladderRanks([10, 11, 12])).toEqual([
      { id: 10, rank: 4, ladder: 0 },
      { id: 11, rank: 3, ladder: 1 },
      { id: 12, rank: 2, ladder: 2 },
    ])
  })

  it('keeps everyone past the fourth place on rank 1, under the group creator', () => {
    expect(ladderRanks([1, 2, 3, 4, 5]).map((item) => item.rank)).toEqual([4, 3, 2, 1, 1])
  })

  it('sorts a shared bottom rank by the saved ladder', () => {
    const rows = positionOrder([
      { id: 2, rank: 1, ladder: 4 },
      { id: 9, rank: 4, ladder: 0 },
      { id: 3, rank: 1, ladder: 3 },
    ])
    expect(rows.map((row) => row.id)).toEqual([9, 3, 2])
    expect(ranksDiffer(rows, [9, 3, 2])).toBe(true)
    expect(ranksDiffer(
      [{ id: 9, rank: 4 }, { id: 3, rank: 3 }],
      [9, 3],
    )).toBe(false)
  })
})
