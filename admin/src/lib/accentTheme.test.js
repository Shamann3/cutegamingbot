import { describe, expect, it } from 'vitest'
import { inkOnAccent } from './accentTheme'

describe('inkOnAccent', () => {
  it('кладёт тёмный текст на светлый и серый акцент', () => {
    expect(inkOnAccent('#FFFFFF')).toBe('#111111')
    expect(inkOnAccent('#C8C8C8')).toBe('#111111')
    expect(inkOnAccent('#9B8BC9')).toBe('#111111')
  })

  it('кладёт белый текст на тёмный акцент', () => {
    expect(inkOnAccent('#1A1A1A')).toBe('#ffffff')
    expect(inkOnAccent('#3A2A6A')).toBe('#ffffff')
  })
})
