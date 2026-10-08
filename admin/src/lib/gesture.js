/**
 * Правила жестов на телефоне: что считать нажатием, а что прокруткой или свайпом.
 * Без DOM и React, поэтому проверяются обычным node.
 */

export const ARM_PX = 8
// Вертикаль чуть в приоритете: страницу листают чаще, чем тянут карточку наискось.
export const LEAN = 1.15

/** Куда ведёт палец: null — ещё не ясно, 'x' — вбок, 'y' — вверх или вниз. */
export function swipeAxis(dx, dy, arm = ARM_PX) {
  if (Math.hypot(dx, dy) < arm) return null
  return Math.abs(dx) > Math.abs(dy) * LEAN ? 'x' : 'y'
}

/**
 * Касание — нажатие или часть прокрутки.
 * moved — палец заметно сдвинулся. scrolledBefore — лента ехала, когда палец коснулся.
 * scrolledDuring — лента прокрутилась, пока палец был на экране.
 * Мышью ленту не останавливают, поэтому для неё важен только сдвиг.
 */
export function tapVerdict({ kind, moved, scrolledBefore, scrolledDuring }) {
  if (moved) return 'scroll'
  if (kind === 'mouse') return 'tap'
  if (scrolledBefore || scrolledDuring) return 'scroll'
  return 'tap'
}
