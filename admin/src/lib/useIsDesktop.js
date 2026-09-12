import { useEffect, useState } from 'react'

/**
 * phone | desktop
 * 1) TG ios/android → phone
 * 2) TG tdesktop/windows/macos/linux → desktop
 * 3) иначе ширина ≥ 901 → desktop
 */

const PHONE_PLATFORMS = new Set(['ios', 'android', 'android_x'])
const DESKTOP_PLATFORMS = new Set(['tdesktop', 'macos', 'linux', 'windows'])
const DESKTOP_MIN_WIDTH = 901

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

  // data-tg-desktop от telegram.js — дополнительный якорь
  try {
    if (document.documentElement.dataset.tgDesktop === '1') return 'desktop'
    if (document.documentElement.dataset.tgDesktop === '0' && PHONE_PLATFORMS.has(platform)) {
      return 'phone'
    }
  } catch {
    /* ignore */
  }

  return window.innerWidth >= DESKTOP_MIN_WIDTH ? 'desktop' : 'phone'
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
    const mq = window.matchMedia(`(min-width: ${DESKTOP_MIN_WIDTH}px)`)
    mq.addEventListener?.('change', sync)
    window.addEventListener('resize', sync)
    window.addEventListener('orientationchange', sync)
    const timers = [50, 200, 600, 1500].map((ms) => window.setTimeout(sync, ms))
    return () => {
      mq.removeEventListener?.('change', sync)
      window.removeEventListener('resize', sync)
      window.removeEventListener('orientationchange', sync)
      timers.forEach((id) => window.clearTimeout(id))
    }
  }, [])

  return mode
}

export function useIsDesktop() {
  return useViewportMode() === 'desktop'
}

export function useIsPhone() {
  return useViewportMode() === 'phone'
}
