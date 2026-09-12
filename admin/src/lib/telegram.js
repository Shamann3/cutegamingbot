/**
 * Telegram Mini App viewport + safe-area для admin-панели.
 *
 * ПК: как раньше — expand + requestFullscreen на весь экран.
 * Телефон: то же + safe-area insets под шапку TG / notch.
 */

import { applyViewportModeToDocument } from './useIsDesktop'

function setCssVar(name, value) {
  document.documentElement.style.setProperty(name, value)
}

function n(v) {
  const x = Number(v)
  return Number.isFinite(x) && x > 0 ? x : 0
}

function syncAdminLayoutMode() {
  try {
    applyViewportModeToDocument()
  } catch {
    /* ignore */
  }
}

function isPhoneTelegram(tg) {
  const platform = String(tg?.platform || '').toLowerCase()
  return platform === 'ios' || platform === 'android' || platform === 'android_x'
}

function isDesktopTelegram(tg) {
  // Phone только ios/android. Web/Desktop Mini App на ПК = desktop всегда.
  return !isPhoneTelegram(tg)
}

function mobileChromeFallback(tg, computedTop) {
  // На ПК не раздуваем верхний inset — панель должна быть «в ноль»
  if (!isPhoneTelegram(tg)) return computedTop
  if (computedTop >= 56) return computedTop
  const platform = String(tg?.platform || '').toLowerCase()
  if (platform === 'ios') return Math.max(computedTop, 96)
  if (platform === 'android') return Math.max(computedTop, 72)
  if (window.innerWidth < 820) return Math.max(computedTop, 88)
  return computedTop
}

function syncTelegramViewport(tg) {
  if (!tg) return

  const h =
    Number(tg.viewportStableHeight || tg.viewportHeight || window.innerHeight) ||
    window.innerHeight
  setCssVar('--tg-viewport-stable-height', `${Math.round(h)}px`)
  setCssVar('--app-vh', `${Math.round(h)}px`)

  const content = tg.contentSafeAreaInset || {}
  const safe = tg.safeAreaInset || {}

  const safeTop = n(safe.top)
  const safeBottom = n(safe.bottom)
  const safeLeft = n(safe.left)
  const safeRight = n(safe.right)
  const contentTop = n(content.top)
  const contentBottom = n(content.bottom)
  const contentLeft = n(content.left)
  const contentRight = n(content.right)

  let top = safeTop + contentTop
  let bottom = safeBottom + contentBottom
  let left = safeLeft + contentLeft
  let right = safeRight + contentRight

  // На desktop Telegram insets часто шумят — обнуляем верх, чтобы не было «полосы телефона»
  if (isDesktopTelegram(tg)) {
    top = 0
    // боковые/низ оставляем если клиент реально отдаёт
  } else {
    top = mobileChromeFallback(tg, top)
  }

  setCssVar('--tg-safe-top', `${isDesktopTelegram(tg) ? 0 : safeTop}px`)
  setCssVar('--tg-safe-bottom', `${bottom}px`)
  setCssVar('--tg-safe-left', `${left}px`)
  setCssVar('--tg-safe-right', `${right}px`)
  setCssVar('--tg-content-top', `${Math.round(top)}px`)
  setCssVar('--tg-content-bottom', `${Math.round(bottom)}px`)

  document.documentElement.dataset.tgViewport = '1'
  document.documentElement.dataset.tgInsetTop = String(Math.round(top))
  document.documentElement.dataset.tgDesktop = isDesktopTelegram(tg) ? '1' : '0'
  document.documentElement.dataset.tgPlatform = String(tg.platform || 'unknown')
  document.documentElement.classList.toggle('tg-fullscreen', Boolean(tg.isFullscreen))
  document.documentElement.classList.toggle('tg-webapp', true)
  syncAdminLayoutMode()
}

function bindViewportSync(tg) {
  const sync = () => syncTelegramViewport(tg)
  sync()

  try {
    tg.onEvent?.('viewportChanged', sync)
    tg.onEvent?.('safeAreaChanged', sync)
    tg.onEvent?.('contentSafeAreaChanged', sync)
    tg.onEvent?.('fullscreenChanged', sync)
  } catch {
    /* older clients */
  }

  window.addEventListener('resize', sync)
  window.visualViewport?.addEventListener?.('resize', sync)
}

/**
 * Как в исходной ПК-версии: expand + requestFullscreen всегда.
 * НЕ вызываем exitFullscreen — из‑за него ПК переставал быть на весь экран.
 */
function applyTelegramViewport(tg) {
  if (!tg) return

  try {
    tg.expand()
  } catch {
    /* ignore */
  }

  if (typeof tg.requestFullscreen === 'function' && !tg.isFullscreen) {
    try {
      tg.requestFullscreen()
    } catch {
      /* уже fullscreen или клиент отклонил */
    }
  }

  syncTelegramViewport(tg)
}

export function initAdminTelegram() {
  const tg = window.Telegram?.WebApp
  if (!tg) {
    setCssVar('--tg-safe-top', '0px')
    setCssVar('--tg-safe-bottom', '0px')
    setCssVar('--tg-safe-left', '0px')
    setCssVar('--tg-safe-right', '0px')
    setCssVar('--tg-content-top', '0px')
    setCssVar('--tg-content-bottom', '0px')
    setCssVar('--tg-viewport-stable-height', `${window.innerHeight}px`)
    document.documentElement.dataset.tgDesktop = window.innerWidth >= 901 ? '1' : '0'
    syncAdminLayoutMode()
    return null
  }

  tg.ready()

  const desktop = isDesktopTelegram(tg)
  document.documentElement.dataset.tgDesktop = desktop ? '1' : '0'
  document.documentElement.dataset.tgPlatform = String(tg.platform || 'unknown')
  syncAdminLayoutMode()

  try {
    tg.setHeaderColor?.('#050508')
    tg.setBackgroundColor?.('#050508')
  } catch {
    /* ignore */
  }

  try {
    tg.disableVerticalSwipes?.()
  } catch {
    /* ignore */
  }

  // Как раньше на ПК: несколько попыток fullscreen при входе
  applyTelegramViewport(tg)
  requestAnimationFrame(() => applyTelegramViewport(tg))
  window.setTimeout(() => applyTelegramViewport(tg), 120)
  window.setTimeout(() => applyTelegramViewport(tg), 400)
  if (!desktop) {
    window.setTimeout(() => applyTelegramViewport(tg), 900)
  }

  bindViewportSync(tg)

  // Если клиент вышел из fullscreen — снова просим (ПК-поведение)
  try {
    tg.onEvent?.('viewportChanged', () => {
      if (!tg.isFullscreen) applyTelegramViewport(tg)
    })
  } catch {
    /* ignore */
  }

  return tg
}

export function getTelegramUser() {
  const user = window.Telegram?.WebApp?.initDataUnsafe?.user
  if (!user?.id) return null
  return user
}
