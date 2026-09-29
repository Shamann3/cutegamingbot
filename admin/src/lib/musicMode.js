import { useRef, useState } from 'react'

const STORAGE_KEY = 'cf_admin_music_volume'
// Громкость, на которую встаёт ползунок при первом клике «включить» —
// сам вход в панель всегда стартует с 0, пока админ явно не прибавит звук.
const UNMUTE_FALLBACK_VOLUME = 0.55

function clamp(value) {
  if (Number.isNaN(value)) return 0
  return Math.max(0, Math.min(1, value))
}

/** 0 — тишина, 1 — полная громкость файла. Квадрат: низкие проценты реально тихие. */
export function musicGain(volume) {
  const level = clamp(Number(volume))
  if (level <= 0) return 0
  return level * level
}

function publishMusicVolume(volume) {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent('epsilon-music-set', { detail: volume }))
}

export function useMusicMode() {
  const [volume, setVolumeState] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored !== null) return clamp(Number(stored))
    } catch { /* ignore */ }
    return 0
  })

  const lastVolumeRef = useRef(volume > 0 ? volume : UNMUTE_FALLBACK_VOLUME)

  const setVolume = (next) => {
    const clamped = clamp(next)
    setVolumeState(clamped)
    if (clamped > 0) lastVolumeRef.current = clamped
    try { localStorage.setItem(STORAGE_KEY, String(clamped)) } catch { /* ignore */ }
    publishMusicVolume(clamped)
  }

  const toggleMute = () => {
    setVolume(volume > 0 ? 0 : lastVolumeRef.current)
  }

  return { volume, setVolume, toggleMute, musicEnabled: volume > 0 }
}
