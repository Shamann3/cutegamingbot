import { useEffect, useState } from 'react'

/**
 * phone | desktop
 *
 * Phone ТОЛЬКО на реальных мобильных клиентах Telegram (ios / android).
 * Всё остальное (tdesktop, windows, macos, linux, web, unknown) = desktop.
 *
 * Раньше web + узкое окно Mini App на ПК ошибочно давало phone —
 * и ПК получал drawer/телефонную вёрстку вместо сайдбара.
 */

const PHONE_PLATFORMS = new Set(['ios', 'android', 'android_x'])
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

  // Явный телефон Telegram — только phone
  if (PHONE_PLATFORMS.has(platform)) return 'phone'

  // Любая другая TG-платформа (в т.ч. web/weba в Desktop) — desktop
  if (platform) return 'desktop'

  // Без Telegram (локальный браузер): ширина
  return widthIsDesktop() ? 'desktop' : 'phone'
}

export function applyViewportModeToDocument(mode = detectViewportMode()) {
  if (typeof document === 'undefined') return mode
  const safe = mode === 'phone' ? 'phone' : 'desktop'
  const root = document.documentElement
  root.dataset.viewport = safe
  root.classList.toggle('is-phone', safe === 'phone')
  root.classList.toggle('is-desktop', safe === 'desktop')
  root.dataset.tgDesktop = safe === 'desktop' ? '1' : '0'
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
