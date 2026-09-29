import { describe, expect, it } from 'vitest'
import { previewAccessFromDefaults } from './panelPreview'

describe('previewAccessFromDefaults', () => {
  it('keeps open pages and only the open inner tabs', () => {
    const access = previewAccessFromDefaults({
      users: true,
      economy: false,
      'staff.applications': true,
      'staff.salaries': false,
      staff: true,
    })
    expect(access.sections).toEqual(['users', 'staff'])
    expect(access.tabs.staff).toEqual(['applications'])
    expect(access.tabs.economy).toBeUndefined()
  })

  it('leaves a page without child keys unfiltered', () => {
    const access = previewAccessFromDefaults({ dashboard: true })
    expect(access.sections).toEqual(['dashboard'])
    expect(access.tabs.dashboard).toBeUndefined()
  })
})
