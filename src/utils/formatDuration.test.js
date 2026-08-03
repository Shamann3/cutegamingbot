import { describe, expect, it } from 'vitest'
import { formatDurationRu, formatDurationRuLong } from './formatDuration'

const sec = (n) => n * 1000
const min = (n) => n * 60 * 1000
const hour = (n) => n * 60 * 60 * 1000
const day = (n) => n * 24 * 60 * 60 * 1000

describe('formatDurationRu', () => {
  it('shows seconds under a minute', () => {
    expect(formatDurationRu(sec(45))).toBe('45 сек.')
  })

  it('shows minutes and seconds under an hour', () => {
    expect(formatDurationRu(min(5) + sec(12))).toBe('5 мин. 12 сек.')
  })

  it('shows hours and minutes', () => {
    expect(formatDurationRu(hour(2) + min(15))).toBe('2 ч. 15 мин.')
  })

  it('shows days hours minutes instead of raw MM:SS', () => {
    // formerly looked like "122:32"
    expect(formatDurationRu(hour(122) + min(32))).toBe('5 д. 2 ч. 32 мин.')
  })

  it('supports months', () => {
    expect(formatDurationRu(day(40))).toBe('1 мес. 10 д.')
  })

  it('long form is readable', () => {
    expect(formatDurationRuLong(day(2) + hour(5))).toContain('дня')
    expect(formatDurationRuLong(day(2) + hour(5))).toContain('часов')
  })
})
