import { describe, expect, it } from 'vitest'
import { formatUsd, kutQuote, starWords } from './kutRate'

describe('kut quote', () => {
  it('prices one kut as one star after Telegram keeps 30 percent', () => {
    const quote = kutQuote('1')
    expect(quote.stars).toBe(1)
    expect(quote.netUsd).toBeCloseTo(0.013, 6)
    expect(quote.grossUsd).toBeCloseTo(0.013 / 0.7, 6)
    expect(formatUsd(quote.netUsd)).toBe('$0.013')
    expect(starWords(1)).toBe('1 звезда')
    expect(starWords(2)).toBe('2 звезды')
    expect(starWords(5)).toBe('5 звёзд')
  })

  it('scales a larger sum', () => {
    const quote = kutQuote('10')
    expect(quote.kut).toBe(10)
    expect(quote.stars).toBe(10)
    expect(quote.netUsd).toBeCloseTo(0.13, 6)
    expect(kutQuote('').kut).toBe(0)
  })
})
