import { useEffect, useState } from 'react'

/**
 * Режим вёрстки панели: phone | desktop.
 *
 * Приоритет:
 * 1) Платформа Telegram (ios/android → phone, tdesktop/web → desktop)
 * 2) Иначе ширина + pointer (браузер без TG / неизвестная платформа)
 *
 * Важно: узкое окно на ПК Telegram остаётся desktop-вёрсткой;
 * широкий iPhone в landscape остаётся phone-вёрсткой.
 */

const PHONE_PLATFORMS = new Set(['ios', 'android', 'android_x'])
const DESKTOP_PLATFORMS = new Set([
  'tdesktop',
  'web',
  'weba',
  'webk',
  'macos',
  'linux',
  'windows',
])

function telegramPlatform() {
  try {
    return String(window.Telegram?.WebApp?.platform || '').toLowerCase()
  } catch {
    return ''
  }
}

export function detectViewportMode() {
  if (typeof window === 'undefined') return 'desktop'

  const platform = telegramPlatform()
  if (PHONE_PLATFORMS.has(platform)) return 'phone'
  if (DESKTOP_PLATFORMS.has(platform)) return 'desktop'

  const narrow = window.matchMedia('(max-width: 900px)').matches
  const coarse = window.matchMedia('(pointer: coarse)').matches
  const fineWide =
    window.matchMedia('(min-width: 901px)').matches &&
    window.matchMedia('(pointer: fine)').matches

  if (fineWide) return 'desktop'
  if (narrow || coarse) return 'phone'
  return 'desktop'
}

export function applyViewportModeToDocument(mode = detectViewportMode()) {
  if (typeof document === 'undefined') return mode
  const root = document.documentElement
  root.dataset.viewport = mode
  root.classList.toggle('is-phone', mode === 'phone')
  root.classList.toggle('is-desktop', mode === 'desktop')
  return mode
}

export function useViewportMode() {
  const [mode, setMode] = useState(() => detectViewportMode())

  useEffect(() => {
    const sync = () => setMode(applyViewportModeToDocument())
    sync()

    const mqWidth = window.matchMedia('(max-width: 900px)')
    const mqPointer = window.matchMedia('(pointer: coarse)')
    mqWidth.addEventListener?.('change', sync)
    mqPointer.addEventListener?.('change', sync)
    window.addEventListener('resize', sync)
    window.addEventListener('orientationchange', sync)

    return () => {
      mqWidth.removeEventListener?.('change', sync)
      mqPointer.removeEventListener?.('change', sync)
      window.removeEventListener('resize', sync)
      window.removeEventListener('orientationchange', sync)
    }
  }, [])

  return mode
}

/** Live: true на desktop-вёрстке (ПК / Telegram Desktop / широкий fine-pointer). */
export function useIsDesktop() {
  return useViewportMode() === 'desktop'
}

/** Live: true на phone-вёрстке (iOS/Android TG / узкий/тач). */
export function useIsPhone() {
  return useViewportMode() === 'phone'
}
