/** Сезон фермы: весна / лето / осень / зима. */

export const SEASON_MODES = {
  AUTO: 'auto',
  SPRING: 'spring',
  SUMMER: 'summer',
  AUTUMN: 'autumn',
  WINTER: 'winter',
}

export const SEASON_MODE_ORDER = [
  SEASON_MODES.AUTO,
  SEASON_MODES.SPRING,
  SEASON_MODES.SUMMER,
  SEASON_MODES.AUTUMN,
  SEASON_MODES.WINTER,
]

/** Реальные сезоны (без auto). */
export const SEASON_VALUES = [
  SEASON_MODES.SPRING,
  SEASON_MODES.SUMMER,
  SEASON_MODES.AUTUMN,
  SEASON_MODES.WINTER,
]

export const SEASON_STORAGE_KEY = 'cute_farm_season_mode'

/**
 * Календарь (умеренный):
 * весна  март–май
 * лето   июнь–август
 * осень  сентябрь–октябрь
 * зима   ноябрь–февраль
 */
export function calendarSeason(date = new Date()) {
  const month = date.getMonth() + 1 // 1–12
  if (month === 11 || month === 12 || month === 1 || month === 2) {
    return SEASON_MODES.WINTER
  }
  if (month >= 3 && month <= 5) return SEASON_MODES.SPRING
  if (month >= 6 && month <= 8) return SEASON_MODES.SUMMER
  return SEASON_MODES.AUTUMN
}

export function resolveSeason(mode, date = new Date()) {
  if (SEASON_VALUES.includes(mode)) return mode
  return calendarSeason(date)
}

export function seasonLabel(season) {
  switch (season) {
    case SEASON_MODES.SPRING:
      return 'Весна'
    case SEASON_MODES.AUTUMN:
      return 'Осень'
    case SEASON_MODES.WINTER:
      return 'Зима'
    default:
      return 'Лето'
  }
}

export function seasonModeLabel(mode) {
  if (mode === SEASON_MODES.AUTO) return 'Авто'
  return seasonLabel(mode)
}

export function seasonModeDesc(mode, resolved) {
  if (mode === SEASON_MODES.AUTO) {
    return `По дате · сейчас ${seasonLabel(resolved).toLowerCase()}`
  }
  switch (mode) {
    case SEASON_MODES.SPRING:
      return 'Цветение, свежая зелень и лёгкий воздух'
    case SEASON_MODES.SUMMER:
      return 'Тёплый лес, золото и светлячки'
    case SEASON_MODES.AUTUMN:
      return 'Янтарь листвы, туман и урожай'
    case SEASON_MODES.WINTER:
      return 'Гирлянды, ёлочки, снег и холодное золото'
    default:
      return ''
  }
}

export function seasonAutoHint() {
  return 'Авто: весна март–май · лето июнь–авг · осень сен–окт · зима ноя–фев'
}
