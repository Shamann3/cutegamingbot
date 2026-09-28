/**
 * Модель прогресса экрана загрузки.
 *
 * Пока данные не пришли, полоса не доходит до конца, но и не замирает:
 * после основной фазы она продолжает медленно ползти к BOOT_CREEP_MAX.
 * Когда данные пришли, полоса плавно (без скачка) догоняет обычный ход.
 */

export const BOOT_HOLD_CAP = 0.9
export const BOOT_CREEP_MAX = 0.985
export const BOOT_CREEP_MS = 1400
export const BOOT_BLEND_MS = 280

const clamp01 = (value) => Math.min(1, Math.max(0, value))
const easeOut = (t) => 1 - Math.pow(1 - clamp01(t), 2)

/** Ход полосы в момент elapsed. waiting — данные ещё не готовы. */
export function bootProgressAt(elapsed, duration, waiting) {
  const linear = duration > 0 ? clamp01(elapsed / duration) : 1
  const eased = easeOut(linear)
  if (!waiting) return eased
  if (linear < 1) return eased * BOOT_HOLD_CAP
  const over = Math.max(0, elapsed - duration)
  return BOOT_CREEP_MAX - (BOOT_CREEP_MAX - BOOT_HOLD_CAP) * Math.exp(-over / BOOT_CREEP_MS)
}

/** Плавный переход от значения from к target за BOOT_BLEND_MS. */
export function blendProgress(from, target, sinceMs, blendMs = BOOT_BLEND_MS) {
  if (!(blendMs > 0)) return target
  const t = easeOut(sinceMs / blendMs)
  return from + (target - from) * t
}

/**
 * Итоговое значение полосы.
 * readyAt / readyFrom — момент и значение, когда пришли данные (или null).
 */
export function bootProgressFrame({ elapsed, duration, needsData, readyAt, readyFrom }) {
  if (!needsData) return bootProgressAt(elapsed, duration, false)
  if (readyAt == null) return bootProgressAt(elapsed, duration, true)
  const target = bootProgressAt(elapsed, duration, false)
  return Math.max(readyFrom, blendProgress(readyFrom, target, elapsed - readyAt))
}

/** Можно уходить с экрана: полоса дошла до конца. */
export function bootIsComplete(value) {
  return value >= 0.999
}
