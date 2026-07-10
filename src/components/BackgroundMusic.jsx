import { useEffect, useRef } from 'react'
import { useOnboardingOptional } from '../context/OnboardingContext'
import { useSettings } from '../context/SettingsContext'

const TRACK_URL = '/assets/track.mp3'
const FADE_IN_MS = 2000
const FADE_OUT_MS = 600
const VOLUME_FADE_MS = 350

function runVolumeFade(audio, targetVolume, durationMs, cancelRef) {
  const startVolume = audio.volume
  const startTime = performance.now()

  if (cancelRef.current) cancelRef.current()
  let rafId = 0

  cancelRef.current = () => {
    cancelAnimationFrame(rafId)
    cancelRef.current = null
  }

  return new Promise((resolve) => {
    const tick = (now) => {
      const progress = Math.min(1, (now - startTime) / durationMs)
      audio.volume = startVolume + (targetVolume - startVolume) * progress
      if (progress < 1) {
        rafId = requestAnimationFrame(tick)
      } else {
        cancelRef.current = null
        resolve()
      }
    }
    rafId = requestAnimationFrame(tick)
  })
}

export default function BackgroundMusic() {
  const onboarding = useOnboardingOptional()
  const { soundEnabled, musicGain, musicVolume } = useSettings()
  const audioRef = useRef(null)
  const fadeCancelRef = useRef(null)
  const playingRef = useRef(false)
  const musicGainRef = useRef(musicGain)

  musicGainRef.current = musicGain

  const readyForMusic = Boolean(
    onboarding
    && !onboarding.starting
    && !onboarding.visible,
  )

  const shouldPlayMusic = readyForMusic && soundEnabled && musicVolume > 0

  useEffect(() => {
    const audio = new Audio(TRACK_URL)
    audio.loop = true
    audio.preload = 'auto'
    audio.volume = 0
    audioRef.current = audio

    return () => {
      if (fadeCancelRef.current) fadeCancelRef.current()
      playingRef.current = false
      audio.pause()
      audio.removeAttribute('src')
      audio.load()
      audioRef.current = null
    }
  }, [])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return undefined

    let cancelled = false

    const stopMusic = async () => {
      playingRef.current = false
      if (audio.paused && audio.volume <= 0.001) return
      await runVolumeFade(audio, 0, FADE_OUT_MS, fadeCancelRef)
      if (!cancelled) {
        audio.pause()
        audio.currentTime = 0
      }
    }

    const startMusic = async () => {
      playingRef.current = true
      audio.volume = 0
      try {
        await audio.play()
      } catch {
        // Браузер может требовать жест - повторим на pointerdown ниже.
      }
      if (cancelled) return
      await runVolumeFade(audio, musicGainRef.current, FADE_IN_MS, fadeCancelRef)
    }

    if (shouldPlayMusic) {
      startMusic()
    } else {
      stopMusic()
    }

    return () => {
      cancelled = true
      if (fadeCancelRef.current) fadeCancelRef.current()
    }
  }, [shouldPlayMusic])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio || !playingRef.current || !shouldPlayMusic) return undefined

    runVolumeFade(audio, musicGain, VOLUME_FADE_MS, fadeCancelRef)
    return () => {
      if (fadeCancelRef.current) fadeCancelRef.current()
    }
  }, [musicGain, shouldPlayMusic])

  useEffect(() => {
    if (!shouldPlayMusic) return undefined

    const unlock = () => {
      const audio = audioRef.current
      if (!audio || !audio.paused) return
      audio.play().catch(() => {})
    }

    window.addEventListener('pointerdown', unlock, { passive: true })
    return () => window.removeEventListener('pointerdown', unlock)
  }, [shouldPlayMusic])

  return null
}
