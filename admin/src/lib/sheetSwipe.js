/**
 * Жест закрытия нижнего листа.
 * Далеко или коротко, но быстро — закрыть. Иначе вернуть на место.
 */
export function sheetSwipeDecision({ dy, velocity, height }) {
  const travel = Number(dy) || 0
  if (travel <= 0) return 'stay'
  const limit = Math.max(1, Number(height) || 320)
  const far = travel >= Math.min(140, limit * 0.28)
  const flung = velocity >= 0.55 && travel >= 36
  return far || flung ? 'close' : 'stay'
}

export function swipeVelocity(samples) {
  if (!samples || samples.length < 2) return 0
  const first = samples[0]
  const last = samples[samples.length - 1]
  return (last.y - first.y) / Math.max(16, last.t - first.t)
}
