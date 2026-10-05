import { afterEach, describe, expect, it, vi } from 'vitest'
import { clampChance, decideMeme, parseExcludedIds, MEME_VOLUME, LOGO_MEME_VOLUME } from './memeSounds'

describe('meme mode', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('keeps the default chance and a fixed volume', () => {
    expect(clampChance(undefined)).toBe(10)
    expect(clampChance(140)).toBe(100)
    expect(clampChance(-2)).toBe(0)
    expect(MEME_VOLUME).toBe(0.35)
    expect(LOGO_MEME_VOLUME).toBe(0.55)
  })

  it('never rolls a meme for an excluded person', () => {
    expect(decideMeme({ chance: 100, exempt: true, random: () => 0 })).toBe(false)
    expect(decideMeme({ chance: 100, stored: '0', random: () => 0 })).toBe(false)
    expect(decideMeme({ chance: 10, stored: '1', random: () => 0.99 })).toBe(true)
  })

  it('uses the chance only for a fresh visit', () => {
    expect(decideMeme({ chance: 10, random: () => 0.09 })).toBe(true)
    expect(decideMeme({ chance: 10, random: () => 0.1 })).toBe(false)
    expect(parseExcludedIds('12, 12\n8 abc')).toEqual([12, 8])
  })
})