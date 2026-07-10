import { useEffect, useRef } from 'react'

const TRACK_URL = `${import.meta.env.BASE_URL}track.mp3`
const FADE_MS = 900

function runFade(audio, targetVolume, durationMs, cancelRef) {
  if (cancelRef.current) cancelRef.current()
  const startVolume = audio.volume
  const startTime = performance.now()
  let rafId = 0

  cancelRef.current = () => cancelAnimationFrame(rafId)

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

// Играет с момента входа в панель (после логина/регистрации) и до выхода.
// volume (0..1) — источник правды из сайдбара (lib/musicMode.js, хранится
// в localStorage). Переход через 0 плавно гасится/поднимается за FADE_MS,
// а перетаскивание слайдера при уже играющем треке применяется мгновенно —
// иначе управление ощущалось бы залипающим.
export default function PanelBackgroundMusic({ volume = 0 }) {
  const audioRef = useRef(null)
  const cancelFadeRef = useRef(null)
  const wasPlayingRef = useRef(false)
  const volumeRef = useRef(volume)

  useEffect(() => {
    const audio = new Audio(TRACK_URL)
    audio.loop = true
    audio.preload = 'auto'
    audio.volume = 0
    audioRef.current = audio

    return () => {
      if (cancelFadeRef.current) cancelFadeRef.current()
      audio.pause()
      audio.removeAttribute('src')
      audio.load()
      audioRef.current = null
    }
  }, [])

  useEffect(() => {
    volumeRef.current = volume
    const audio = audioRef.current
    if (!audio) return undefined

    let cancelled = false

    const stop = async () => {
      await runFade(audio, 0, FADE_MS, cancelFadeRef)
      if (!cancelled) audio.pause()
      wasPlayingRef.current = false
    }

    const startAndFadeIn = async () => {
      try {
        await audio.play()
      } catch {
        // Требуется жест пользователя — подхватим на следующем клике.
        return
      }
      if (cancelled) return
      wasPlayingRef.current = true
      await runFade(audio, volume, FADE_MS, cancelFadeRef)
    }

    if (volume <= 0) {
      if (wasPlayingRef.current) stop()
    } else if (!wasPlayingRef.current) {
      startAndFadeIn()
    } else {
      // Уже играет — слайдер тянут вживую, применяем без анимации.
      if (cancelFadeRef.current) cancelFadeRef.current()
      audio.volume = volume
    }

    return () => {
      cancelled = true
    }
  }, [volume])

  useEffect(() => {
    const unlock = () => {
      const audio = audioRef.current
      if (!audio || volumeRef.current <= 0 || !audio.paused) return
      audio.play().then(() => {
        wasPlayingRef.current = true
        return runFade(audio, volumeRef.current, FADE_MS, cancelFadeRef)
      }).catch(() => {})
    }
    window.addEventListener('pointerdown', unlock, { passive: true })
    return () => window.removeEventListener('pointerdown', unlock)
  }, [])

  return null
}
