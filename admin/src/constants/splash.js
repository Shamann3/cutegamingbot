export const SPLASH_DARK_PAUSE_MS = 2200
export const SPLASH_LETTER_MS = 72
export const SPLASH_HOLD_MS = 2600
export const SPLASH_FADEOUT_MS = 1700
export const SPLASH_EXIT_STAGGER_MS = 36
export const SPLASH_ENTRANCE_VARIANTS = [
  'splash-enter-up',
  'splash-enter-down',
  'splash-enter-left',
  'splash-enter-right',
  'splash-enter-depth',
  'splash-enter-tilt-left',
  'splash-enter-tilt-right',
  'splash-enter-rise-blur',
]

export function pickEntranceVariant(index, char) {
  if (char === ' ') return 'splash-enter-fade'
  const code = char.charCodeAt(0)
  return SPLASH_ENTRANCE_VARIANTS[(index * 11 + code) % SPLASH_ENTRANCE_VARIANTS.length]
}

export function pickExitVariant(index) {
  const variants = [
    'splash-exit-up',
    'splash-exit-down',
    'splash-exit-left',
    'splash-exit-right',
    'splash-exit-depth',
  ]
  return variants[(index * 5) % variants.length]
}
