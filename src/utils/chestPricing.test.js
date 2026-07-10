import { describe, expect, it } from 'vitest'
import { clampCount, totalStars, buildChestStartPayload, buildChestBotUrl } from './chestPricing'

describe('chestPricing', () => {
  it('clamps count to 1..10', () => {
    expect(clampCount(0)).toBe(1)
    expect(clampCount(1)).toBe(1)
    expect(clampCount(10)).toBe(10)
    expect(clampCount(11)).toBe(10)
    expect(clampCount(3.7)).toBe(3)
    expect(clampCount(NaN)).toBe(1)
  })
  it('computes total stars from price and count', () => {
    expect(totalStars(3, 25)).toBe(75)
    expect(totalStars(1, 25)).toBe(25)
    expect(totalStars(0, 25)).toBe(25) // clamped to 1
  })
  it('builds a telegram-safe start payload', () => {
    expect(buildChestStartPayload(3)).toBe('chest_3')
    expect(buildChestStartPayload(99)).toBe('chest_10')
    expect(/^[A-Za-z0-9_-]+$/.test(buildChestStartPayload(5))).toBe(true)
  })
  it('builds a bot url with the payload', () => {
    expect(buildChestBotUrl(2)).toContain('?start=chest_2')
    expect(buildChestBotUrl(2)).toContain('t.me/')
  })
})
