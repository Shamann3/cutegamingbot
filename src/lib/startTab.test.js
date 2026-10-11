import { describe, expect, it } from 'vitest'
import { getStartTab, pickStartTab, readStartParam } from './telegram'
import { aimedItemIds, resolveStartTab } from '../utils/tradeNav'

describe('readStartParam', () => {
  it('reads the section Telegram put in the launch hash', () => {
    const raw = readStartParam({ hash: '#tgWebAppStartParam=market&tgWebAppVersion=8' })
    expect(raw).toBe('market')
    expect(resolveStartTab(pickStartTab(raw))).toEqual({ tab: 'trade', tradeSegment: 'market' })
  })

  it('reads startapp from the page address used by a private button', () => {
    expect(getStartTab({ search: '?startapp=shop' })).toBe('shop')
    expect(resolveStartTab('shop')).toEqual({ tab: 'trade', tradeSegment: 'shop' })
  })

  it('prefers the signed start_param over the page query', () => {
    expect(getStartTab({
      unsafe: 'inventory',
      search: '?startapp=farm',
    })).toBe('inventory')
  })

  it('ignores an unknown section', () => {
    expect(pickStartTab('not-a-tab')).toBeNull()
    expect(getStartTab({ hash: '#tgWebAppStartParam=' })).toBeNull()
  })

  it('opens a shop item from a water-games button', () => {
    expect(pickStartTab('shop-42')).toBe('shop-42')
    expect(resolveStartTab('shop-42')).toEqual({ tab: 'trade', tradeSegment: 'shop', itemId: '42' })
    expect(resolveStartTab('market-7')).toEqual({ tab: 'trade', tradeSegment: 'market', itemId: '7' })
    expect(aimedItemIds('shop-277')).toEqual({ shopItemId: '277', marketItemId: '', ownLot: false })
    expect(aimedItemIds('market-294')).toEqual({ shopItemId: '', marketItemId: '294', ownLot: false })
    expect(aimedItemIds('shop')).toEqual({ shopItemId: '', marketItemId: '', ownLot: false })
    expect(pickStartTab('own-294')).toBe('own-294')
    expect(resolveStartTab('own-294')).toEqual({
      tab: 'trade', tradeSegment: 'market', itemId: '294', ownLot: true,
    })
    expect(aimedItemIds('own-294')).toEqual({ shopItemId: '', marketItemId: '294', ownLot: true })
  })

  it('keeps craft and farm as their own screens', () => {
    expect(resolveStartTab(pickStartTab('craft'))).toEqual({ tab: 'craft', tradeSegment: 'shop' })
    expect(resolveStartTab(pickStartTab('farm'))).toEqual({ tab: 'farm', tradeSegment: 'shop' })
  })
})
