import { describe, it, expect } from 'vitest'
import { makeCraftKey } from './craftKey.js'

const RE = /^[a-z][a-z0-9_]{1,48}$/

describe('makeCraftKey', () => {
  it('produces a backend-valid key', () => {
    expect(makeCraftKey('3', '7', '9')).toMatch(RE)
  })
  it('is order-independent in the ingredient pair', () => {
    expect(makeCraftKey('3', '7', '9')).toBe(makeCraftKey('3', '9', '7'))
  })
  it('always starts with a letter even for numeric ids', () => {
    expect(makeCraftKey('300', '301', '302')[0]).toMatch(/[a-z]/)
  })
})
