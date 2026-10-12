import { useEffect, useRef } from 'react'
import { musicGain } from '../lib/musicMode'

const PANEL_TRACK = new URL('../../public/track.mp3', import.meta.url).href

function setLevel(audio, raw) {
  const level = musicGain(raw)
  try {
    audio.volume = level
  } catch {
    return
  }
  if (level <= 0) {
    if (!audio.paused) audio.pause()
    return
  }
  if (!audio.paused) return
  const played = audio.play()
  if (played && typeof played.catch === 'function') played.catch(() => {})
}

export default function PanelBackgroundMusic({ volume = 0 }) {
  const audioRef = useRef(null)
  const volumeRef = useRef(volume)
  volumeRef.current = volume

  useEffect(() => {
    const audio = new Audio()
    audio.loop = true
    audio.preload = 'auto'
    audio.src = PANEL_TRACK
    audio.volume = 0
    audioRef.current = audio
    return () => {
      audio.pause()
      audio.removeAttribute('src')
      audio.load()
      audioRef.current = null
    }
  }, [])

  useEffect(() => {
    const audio = audioRef.current
    if (audio) setLevel(audio, volume)
  }, [volume])

  useEffect(() => {
    const apply = (raw) => {
      const audio = audioRef.current
      if (audio) setLevel(audio, raw)
    }
    const onSet = (event) => apply(event.detail)
    const unlock = () => {
      if (volumeRef.current > 0) apply(volumeRef.current)
    }
    window.addEventListener('epsilon-music-set', onSet)
    window.addEventListener('pointerdown', unlock, { passive: true })
    return () => {
      window.removeEventListener('epsilon-music-set', onSet)
      window.removeEventListener('pointerdown', unlock)
    }
  }, [])

  return null
}
