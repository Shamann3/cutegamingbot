export const ORBIT_PERIOD_MS = { full: 2400, lite: 2400 }
export const FUSE_DURATION_MS = { full: 1550, lite: 0 }
export const ALIGN_TOLERANCE_DEG = 14

export function orbitPeriodMs(tier) {
  return ORBIT_PERIOD_MS[tier] ?? ORBIT_PERIOD_MS.full
}

export function fuseDurationMs(tier) {
  return FUSE_DURATION_MS[tier] ?? FUSE_DURATION_MS.full
}

/** A clockwise, B counter-clockwise; B starts opposite (180°). */
export function orbitAngles(elapsedMs, periodMs, initialB = 180) {
  const omega = 360 / periodMs
  const angleA = (elapsedMs * omega) % 360
  const angleB = (initialB - elapsedMs * omega + 360) % 360
  return { angleA, angleB }
}

export function areOrbitsAligned(angleA, angleB, toleranceDeg = ALIGN_TOLERANCE_DEG) {
  let diff = Math.abs(angleA - angleB)
  diff = Math.min(diff, 360 - diff)
  return diff <= toleranceDeg
}

export function fuseAngles(elapsedMs, durationMs, startA, startB) {
  const p = Math.min(1, Math.max(0, elapsedMs / durationMs))
  const ease = 1 - (1 - p) ** 3
  const spin = 540 * ease
  return {
    angleA: startA + spin,
    angleB: startB - spin,
    merge: ease,
    scale: Math.max(0, 1 - ease * 0.92),
    orbOpacity: Math.max(0, 1 - ease * 0.95),
  }
}

export function msUntilNextAlignment(orbitEpochMs, periodMs, now = performance.now()) {
  const half = periodMs / 2
  const elapsed = now - orbitEpochMs
  const mod = ((elapsed % half) + half) % half
  const toleranceMs = (ALIGN_TOLERANCE_DEG / 360) * periodMs
  if (mod <= toleranceMs || mod >= half - toleranceMs) return 0
  return half - mod
}
