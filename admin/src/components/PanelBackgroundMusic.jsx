import { useEffect, useRef } from 'react'
import { musicGain } from '../lib/musicMode'

const PANEL_TRACK = `${import.meta.env.BASE_URL}track.mp3`

// Громкость применяется сразу, внутри жеста ползунка.
// Иначе play() из эффекта после отрисовки браузер молча отклоняет,
// а плавное затухание съедало процент, пока палец ещё на шкале.
export default function PanelBackgroundMusic({ volume = 0 }) {
  const audioRef = useRef(null)
  const volumeRef = useRef(volume)
  volumeRef.current = volume

  const apply = (raw) => {
    const audio = audioRef.current
    if (!audio) return
    const level = musicGain(raw)
    audio.volume = level
    if (level <= 0) {
      audio.pause()
      return
    }
    const played = audio.play()
    if (played && typeof played.catch === 'function') played.catch(() => {})
  }

  useEffect(() => {
    const audio = new Audio()
    audio.loop = true
    audio.preload = 'auto'
    audio.src = PANEL_TRACK
    audio.volume = musicGain(volumeRef.current)
    audioRef.current = audio
    return () => {
      audio.pause()
      audio.removeAttribute('src')
      audio.load()
      audioRef.current = null
    }
  }, [])

  useEffect(() => {
    apply(volume)
  }, [volume])

  useEffect(() => {
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
