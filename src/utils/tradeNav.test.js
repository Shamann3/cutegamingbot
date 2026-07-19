import { describe, expect, it } from 'vitest'
import { resolveStartTab } from './tradeNav'

describe('resolveStartTab', () => {
  it('maps legacy "shop" deep-link to the trade tab on the shop segment', () => {
    expect(resolveStartTab('shop')).toEqual({ tab: 'trade', tradeSegment: 'shop' })
  })

  it('maps legacy "market" deep-link to the trade tab on the market segment', () => {
    expect(resolveStartTab('market')).toEqual({ tab: 'trade', tradeSegment: 'market' })
  })

  it('defaults a direct "trade" deep-link to the shop segment', () => {
    expect(resolveStartTab('trade')).toEqual({ tab: 'trade', tradeSegment: 'shop' })
  })

  it('passes through unrelated tabs unchanged', () => {
    expect(resolveStartTab('quests')).toEqual({ tab: 'quests', tradeSegment: 'shop' })
    expect(resolveStartTab('farm')).toEqual({ tab: 'farm', tradeSegment: 'shop' })
  })
})
