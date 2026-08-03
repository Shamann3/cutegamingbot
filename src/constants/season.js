/** Сезон фермы: лето / зима. */

export const SEASON_MODES = {
  AUTO: 'auto',
  SUMMER: 'summer',
  WINTER: 'winter',
}

export const SEASON_MODE_ORDER = [
  SEASON_MODES.AUTO,
  SEASON_MODES.SUMMER,
  SEASON_MODES.WINTER,
]

export const SEASON_STORAGE_KEY = 'cute_farm_season_mode'

/** Зима: ноябрь–февраль (когда зелень выглядит чужеродно). */
export function calendarSeason(date = new Date()) {
  const month = date.getMonth() + 1 // 1–12
  if (month === 11 || month === 12 || month === 1 || month === 2) {
    return SEASON_MODES.WINTER
  }
  return SEASON_MODES.SUMMER
}

export function resolveSeason(mode, date = new Date()) {
  if (mode === SEASON_MODES.SUMMER || mode === SEASON_MODES.WINTER) return mode
  return calendarSeason(date)
}

export function seasonLabel(season) {
  return season === SEASON_MODES.WINTER ? 'Зима' : 'Лето'
}

export function seasonModeLabel(mode) {
  if (mode === SEASON_MODES.SUMMER) return 'Лето'
  if (mode === SEASON_MODES.WINTER) return 'Зима'
  return 'Авто'
}

export function seasonModeDesc(mode, resolved) {
  if (mode === SEASON_MODES.AUTO) {
    return `По дате · сейчас ${seasonLabel(resolved).toLowerCase()}`
  }
  if (mode === SEASON_MODES.SUMMER) return 'Тёплый лес и золото'
  return 'Иней, снег и холодное золото'
}
