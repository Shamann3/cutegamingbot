import { PERF_CLOCK_MS, PERF_MODES, isTurboMode } from '../constants/performance'

export function isMobilePerfDevice() {
  if (typeof window === 'undefined') return false
  return (
    window.matchMedia('(hover: none) and (pointer: coarse)').matches
    || window.matchMedia('(max-width: 640px)').matches
  )
}

export function getPerfClockMs(mode) {
  const base = PERF_CLOCK_MS[mode] ?? PERF_CLOCK_MS[PERF_MODES.FULL]
  if (isTurboMode(mode)) return base
  if (isMobilePerfDevice()) return Math.max(base, 1500)
  return base
}

export function bindMobilePerfClass(root = document.documentElement) {
  const apply = () => {
    root.classList.toggle('cute-mobile', isMobilePerfDevice())
  }
  apply()

  const queries = [
    window.matchMedia('(hover: none) and (pointer: coarse)'),
    window.matchMedia('(max-width: 640px)'),
  ]

  queries.forEach((mq) => mq.addEventListener('change', apply))

  return () => {
    queries.forEach((mq) => mq.removeEventListener('change', apply))
    root.classList.remove('cute-mobile')
  }
}
