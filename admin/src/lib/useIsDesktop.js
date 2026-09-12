import { useEffect, useState } from 'react'

/**
 * Режим вёрстки: phone | desktop.
 *
 * Правила (жёстко):
 * 1) Telegram ios/android → phone
 * 2) Telegram tdesktop / windows / macos / linux → desktop
 * 3) Иначе только по ширине: ≥901px → desktop, иначе phone
 *
 * НЕ используем pointer:coarse — на тачскрин-ноутбуках ПК
 * ошибочно становился «телефоном».
 */

const PHONE_PLATFORMS = new Set(['ios', 'android', 'android_x'])
const DESKTOP_PLATFORMS = new Set([
  'tdesktop',
  'macos',
  'linux',
  'windows',
])

/** web/weba/webk — неоднозначно (может быть и телефонный браузер TG) */
const AMBIGUOUS_PLATFORMS = new Set(['web', 'weba', 'webk'])

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
    if (window.matchMedia(`(min-width: ${DESKTOP_MIN_WIDTH}px)`).matches) return true
  } catch {
    /* ignore */
  }
  return window.innerWidth >= DESKTOP_MIN_WIDTH
}

export function detectViewportMode() {
  if (typeof window === 'undefined') return 'desktop'

  const platform = telegramPlatform()

  if (PHONE_PLATFORMS.has(platform)) return 'phone'
  if (DESKTOP_PLATFORMS.has(platform)) return 'desktop'

  // web / неизвестно / без TG — только ширина
  if (AMBIGUOUS_PLATFORMS.has(platform) || !platform) {
    return widthIsDesktop() ? 'desktop' : 'phone'
  }

  return widthIsDesktop() ? 'desktop' : 'phone'
}

export function applyViewportModeToDocument(mode = detectViewportMode()) {
  if (typeof document === 'undefined') return mode
  const root = document.documentElement
  root.dataset.viewport = mode
  root.classList.toggle('is-phone', mode === 'phone')
  root.classList.toggle('is-desktop', mode === 'desktop')
  try {
    window.dispatchEvent(new CustomEvent('admin-viewport-change', { detail: { mode } }))
  } catch {
    /* ignore */
  }
  return mode
}

export function useViewportMode() {
  const [mode, setMode] = useState(() => detectViewportMode())

  useEffect(() => {
    const sync = () => setMode(applyViewportModeToDocument())
    sync()

    const mqWidth = window.matchMedia(`(min-width: ${DESKTOP_MIN_WIDTH}px)`)
    mqWidth.addEventListener?.('change', sync)
    window.addEventListener('resize', sync)
    window.addEventListener('orientationchange', sync)
    window.addEventListener('admin-viewport-change', sync)

    // Telegram.WebApp.platform часто появляется чуть позже первого paint
    const t1 = window.setTimeout(sync, 50)
    const t2 = window.setTimeout(sync, 200)
    const t3 = window.setTimeout(sync, 600)
    const t4 = window.setTimeout(sync, 1500)

    return () => {
      mqWidth.removeEventListener?.('change', sync)
      window.removeEventListener('resize', sync)
      window.removeEventListener('orientationchange', sync)
      window.removeEventListener('admin-viewport-change', sync)
      window.clearTimeout(t1)
      window.clearTimeout(t2)
      window.clearTimeout(t3)
      window.clearTimeout(t4)
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
