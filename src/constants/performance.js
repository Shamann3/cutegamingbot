export const PERF_MODES = {
  FULL: 'full',
  LITE: 'lite',
  TURBO: 'turbo',
}

export const PERF_MODE_ORDER = [PERF_MODES.FULL, PERF_MODES.LITE, PERF_MODES.TURBO]

export const PERF_MODE_STORAGE_KEY = 'cute_perf_mode'
export const LITE_MODE_LEGACY_KEY = 'cute_lite_mode'

const BASE_FARM_POLL = Number(import.meta.env.VITE_FARM_POLL_MS) || 15000

export const PERF_POLL_MS = {
  // FULL: relaxed poll - UI clock/timers update locally; farm state need not be fastest.
  [PERF_MODES.FULL]: { farm: Math.max(BASE_FARM_POLL, 20_000), shop: 15_000 },
  [PERF_MODES.LITE]: { farm: BASE_FARM_POLL, shop: 15_000 },
  [PERF_MODES.TURBO]: { farm: Math.max(BASE_FARM_POLL * 2, 30_000), shop: 30_000 },
}

export const PERF_CLOCK_MS = {
  [PERF_MODES.FULL]: 1000,
  [PERF_MODES.LITE]: 1000,
  [PERF_MODES.TURBO]: 2000,
}

export function isLiteOrAbove(mode) {
  return mode === PERF_MODES.LITE || mode === PERF_MODES.TURBO
}

export function isTurboMode(mode) {
  return mode === PERF_MODES.TURBO
}

export function nextPerfMode(mode) {
  const idx = PERF_MODE_ORDER.indexOf(mode)
  const next = PERF_MODE_ORDER[(idx + 1) % PERF_MODE_ORDER.length]
  return next ?? PERF_MODES.FULL
}
