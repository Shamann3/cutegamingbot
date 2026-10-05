import { describe, expect, it } from 'vitest'
import { grantedWide } from './realmRights'

describe('granted disciplines', () => {
  it('shows a wide punishment only when that switch is on', () => {
    const catalog = [
      { id: 'muteall', label: 'Муталл' },
      { id: 'banfull', label: 'Банфулл' },
    ]
    expect(grantedWide(catalog, ['punish_ban', 'banfull']).map((item) => item.id)).toEqual(['banfull'])
    expect(grantedWide(catalog, ['punish_mute'])).toEqual([])
  })
})
