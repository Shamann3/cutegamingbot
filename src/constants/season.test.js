import { describe, expect, it } from 'vitest'
import {
  calendarSeason,
  resolveSeason,
  SEASON_MODES,
} from './season'

describe('calendarSeason', () => {
  it('maps winter months', () => {
    expect(calendarSeason(new Date(2026, 10, 1))).toBe(SEASON_MODES.WINTER) // Nov
    expect(calendarSeason(new Date(2026, 11, 25))).toBe(SEASON_MODES.WINTER) // Dec
    expect(calendarSeason(new Date(2027, 0, 15))).toBe(SEASON_MODES.WINTER) // Jan
    expect(calendarSeason(new Date(2027, 1, 28))).toBe(SEASON_MODES.WINTER) // Feb
  })

  it('maps spring / summer / autumn', () => {
    expect(calendarSeason(new Date(2026, 2, 1))).toBe(SEASON_MODES.SPRING) // Mar
    expect(calendarSeason(new Date(2026, 4, 15))).toBe(SEASON_MODES.SPRING) // May
    expect(calendarSeason(new Date(2026, 5, 1))).toBe(SEASON_MODES.SUMMER) // Jun
    expect(calendarSeason(new Date(2026, 7, 20))).toBe(SEASON_MODES.SUMMER) // Aug
    expect(calendarSeason(new Date(2026, 8, 1))).toBe(SEASON_MODES.AUTUMN) // Sep
    expect(calendarSeason(new Date(2026, 9, 31))).toBe(SEASON_MODES.AUTUMN) // Oct
  })
})

describe('resolveSeason', () => {
  it('honours explicit mode over calendar', () => {
    const winterDay = new Date(2026, 11, 1)
    const summerDay = new Date(2026, 6, 1)
    expect(resolveSeason(SEASON_MODES.SUMMER, winterDay)).toBe(SEASON_MODES.SUMMER)
    expect(resolveSeason(SEASON_MODES.WINTER, summerDay)).toBe(SEASON_MODES.WINTER)
    expect(resolveSeason(SEASON_MODES.SPRING, winterDay)).toBe(SEASON_MODES.SPRING)
    expect(resolveSeason(SEASON_MODES.AUTUMN, summerDay)).toBe(SEASON_MODES.AUTUMN)
    expect(resolveSeason(SEASON_MODES.AUTO, winterDay)).toBe(SEASON_MODES.WINTER)
    expect(resolveSeason(SEASON_MODES.AUTO, new Date(2026, 3, 10))).toBe(SEASON_MODES.SPRING)
  })
})
