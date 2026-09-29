import { describe, expect, it } from 'vitest'
import { sheetSwipeDecision, swipeVelocity } from './sheetSwipe'

describe('sheetSwipeDecision', () => {
  it('закрывает длинный провод и быстрый смах', () => {
    expect(sheetSwipeDecision({ dy: 160, velocity: 0.1, height: 480 })).toBe('close')
    expect(sheetSwipeDecision({ dy: 40, velocity: 0.8, height: 480 })).toBe('close')
  })

  it('короткий медленный сдвиг оставляет лист', () => {
    expect(sheetSwipeDecision({ dy: 24, velocity: 0.1, height: 480 })).toBe('stay')
    expect(sheetSwipeDecision({ dy: -20, velocity: 1, height: 480 })).toBe('stay')
  })

  it('скорость считается по последним точкам пальца', () => {
    expect(swipeVelocity([{ y: 10, t: 0 }, { y: 70, t: 100 }])).toBeCloseTo(0.6)
    expect(swipeVelocity([])).toBe(0)
  })
})