import { describe, expect, it } from 'vitest'
import {
  calendarSeason,
  resolveSeason,
  SEASON_MODES,
} from './season'

describe('season', () => {
  it('marks Nov–Feb as winter', () => {
    expect(calendarSeason(new Date(2026, 10, 1))).toBe(SEASON_MODES.WINTER) // Nov
    expect(calendarSeason(new Date(2026, 11, 25))).toBe(SEASON_MODES.WINTER) // Dec
    expect(calendarSeason(new Date(2027, 0, 15))).toBe(SEASON_MODES.WINTER) // Jan
    expect(calendarSeason(new Date(2027, 1, 28))).toBe(SEASON_MODES.WINTER) // Feb
  })

  it('marks Mar–Oct as summer', () => {
    expect(calendarSeason(new Date(2026, 2, 1))).toBe(SEASON_MODES.SUMMER)
    expect(calendarSeason(new Date(2026, 6, 15))).toBe(SEASON_MODES.SUMMER)
    expect(calendarSeason(new Date(2026, 9, 31))).toBe(SEASON_MODES.SUMMER)
  })

  it('respects manual override', () => {
    const winterDay = new Date(2026, 11, 1)
    expect(resolveSeason(SEASON_MODES.SUMMER, winterDay)).toBe(SEASON_MODES.SUMMER)
    const summerDay = new Date(2026, 6, 1)
    expect(resolveSeason(SEASON_MODES.WINTER, summerDay)).toBe(SEASON_MODES.WINTER)
    expect(resolveSeason(SEASON_MODES.AUTO, winterDay)).toBe(SEASON_MODES.WINTER)
  })
})
