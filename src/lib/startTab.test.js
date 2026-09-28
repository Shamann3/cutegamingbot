import { describe, expect, it } from 'vitest'
import { getStartTab, pickStartTab, readStartParam } from './telegram'
import { resolveStartTab } from '../utils/tradeNav'

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

  it('keeps craft and farm as their own screens', () => {
    expect(resolveStartTab(pickStartTab('craft'))).toEqual({ tab: 'craft', tradeSegment: 'shop' })
    expect(resolveStartTab(pickStartTab('farm'))).toEqual({ tab: 'farm', tradeSegment: 'shop' })
  })
})
