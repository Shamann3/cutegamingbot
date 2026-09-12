import { useEffect, useState } from 'react'

/**
 * phone | desktop — единая логика для CSS и React.
 *
 * 1) TG ios/android → phone
 * 2) TG tdesktop/windows/macos/linux → desktop
 * 3) TG web/weba/webk + ширина ≥901 → desktop
 * 4) иначе ширина ≥901 → desktop, иначе phone
 */

const PHONE_PLATFORMS = new Set(['ios', 'android', 'android_x'])
const DESKTOP_PLATFORMS = new Set(['tdesktop', 'macos', 'linux', 'windows'])
const WEB_PLATFORMS = new Set(['web', 'weba', 'webk'])
const DESKTOP_MIN_WIDTH = 901

function telegramPlatform() {
  try {
    return String(window.Telegram?.WebApp?.platform || '').toLowerCase()
  } catch {
    return ''
  }
}

function widthIsDesktop() {
  try {
    return window.innerWidth >= DESKTOP_MIN_WIDTH
  } catch {
    return true
  }
}

export function detectViewportMode() {
  if (typeof window === 'undefined') return 'desktop'

  const platform = telegramPlatform()

  if (PHONE_PLATFORMS.has(platform)) return 'phone'
  if (DESKTOP_PLATFORMS.has(platform)) return 'desktop'

  try {
    if (document.documentElement.dataset.tgDesktop === '1') return 'desktop'
  } catch {
    /* ignore */
  }

  if (WEB_PLATFORMS.has(platform)) {
    return widthIsDesktop() ? 'desktop' : 'phone'
  }

  return widthIsDesktop() ? 'desktop' : 'phone'
}

export function applyViewportModeToDocument(mode = detectViewportMode()) {
  if (typeof document === 'undefined') return mode
  // Защита от битых значений (раньше из-за бага мог попасть boolean true)
  const safe = mode === 'phone' ? 'phone' : 'desktop'
  const root = document.documentElement
  root.dataset.viewport = safe
  root.classList.toggle('is-phone', safe === 'phone')
  root.classList.toggle('is-desktop', safe === 'desktop')
  return safe
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
