import { describe, it, expect } from 'vitest'
import { contentTabs } from './contentTabs.js'

describe('contentTabs', () => {
  it('omits the map tab when canUseMap is false', () => {
    const ids = contentTabs(false).map((t) => t.id)
    expect(ids).toEqual(['items', 'crops', 'craft', 'quests'])
  })
  it('includes the map tab (before quests) when canUseMap is true', () => {
    const ids = contentTabs(true).map((t) => t.id)
    expect(ids).toEqual(['items', 'crops', 'craft', 'map', 'quests'])
  })
})
