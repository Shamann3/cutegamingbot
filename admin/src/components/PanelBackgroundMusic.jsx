import { useEffect, useRef } from 'react'
import { readCueSoundsEnabled } from '../lib/cueSounds'
import { musicGain } from '../lib/musicMode'

const PANEL_TRACK = `${import.meta.env.BASE_URL}track.mp3`

// Громкость применяется сразу, внутри жеста ползунка.
// Иначе play() из эффекта после отрисовки браузер молча отклоняет,
// а плавное затухание съедало процент, пока палец ещё на шкале.
export default function PanelBackgroundMusic({ volume = 0 }) {
  const audioRef = useRef(null)
  const volumeRef = useRef(volume)
  const allowRef = useRef(readCueSoundsEnabled())
  volumeRef.current = volume

  const apply = (raw) => {
    const audio = audioRef.current
    if (!audio) return
    const level = allowRef.current ? musicGain(raw) : 0
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
    const onCue = (event) => {
      allowRef.current = Boolean(event.detail)
      apply(volumeRef.current)
    }
    const unlock = () => {
      if (allowRef.current && volumeRef.current > 0) apply(volumeRef.current)
    }
    window.addEventListener('epsilon-music-set', onSet)
    window.addEventListener('epsilon-cue-sounds', onCue)
    window.addEventListener('pointerdown', unlock, { passive: true })
    return () => {
      window.removeEventListener('epsilon-music-set', onSet)
      window.removeEventListener('epsilon-cue-sounds', onCue)
      window.removeEventListener('pointerdown', unlock)
    }
  }, [])

  return null
}
