import { readStorage } from '../utils/safeStorage'

export const MUSIC_VOLUME_STORAGE_KEY = 'cute_music_volume'
export const MUSIC_VOLUME_DEFAULT = 35
export const MUSIC_VOLUME_MIN_GAIN = 0.04
export const MUSIC_VOLUME_MAX_GAIN = 0.44

export function musicGainFromPercent(percent) {
  const clamped = Math.max(0, Math.min(100, Number(percent) || 0))
  if (clamped <= 0) return 0
  const t = clamped / 100
  return MUSIC_VOLUME_MIN_GAIN + t * (MUSIC_VOLUME_MAX_GAIN - MUSIC_VOLUME_MIN_GAIN)
}

export function musicVolumeLabel(percent) {
  if (percent <= 0) return 'Выключена'
  if (percent <= 20) return 'Очень тихо'
  if (percent <= 45) return 'Тихо'
  if (percent <= 70) return 'Средне'
  return 'Громче'
}

export function readMusicVolumePercent() {
  const stored = readStorage(MUSIC_VOLUME_STORAGE_KEY)
  const value = Number(stored)
  if (Number.isFinite(value) && value >= 0 && value <= 100) {
    return Math.round(value)
  }
  return MUSIC_VOLUME_DEFAULT
}
