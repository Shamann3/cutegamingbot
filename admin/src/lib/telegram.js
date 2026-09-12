/**
 * Telegram Mini App viewport + safe-area для admin-панели.
 *
 * Важно: safeAreaInset (Dynamic Island / home) и contentSafeAreaInset
 * (✕ / меню Telegram) — РАЗНЫЕ слои. Их нужно СКЛАДЫВАТЬ, иначе
 * шапка Telegram наезжает на topbar панели.
 */

function setCssVar(name, value) {
  document.documentElement.style.setProperty(name, value)
}

function n(v) {
  const x = Number(v)
  return Number.isFinite(x) && x > 0 ? x : 0
}

function isDesktopTelegram(tg) {
  const platform = String(tg?.platform || '').toLowerCase()
  if (
    platform === 'tdesktop' ||
    platform === 'web' ||
    platform === 'weba' ||
    platform === 'macos' ||
    platform === 'linux' ||
    platform === 'windows'
  ) {
    return true
  }
  try {
    return window.innerWidth >= 820 && window.matchMedia?.('(pointer: fine)').matches
  } catch {
    return false
  }
}

function mobileChromeFallback(tg, computedTop) {
  if (isDesktopTelegram(tg)) return computedTop
  // API ещё не отдал insets / старый клиент — запас под шапку TG + notch
  if (computedTop >= 56) return computedTop
  const platform = String(tg?.platform || '').toLowerCase()
  if (platform === 'ios') return Math.max(computedTop, 96)
  if (platform === 'android') return Math.max(computedTop, 72)
  // неизвестная мобильная платформа
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

  // Сумма двух слоёв — канон для fullscreen Mini App
  let top = safeTop + contentTop
  let bottom = safeBottom + contentBottom
  let left = safeLeft + contentLeft
  let right = safeRight + contentRight

  top = mobileChromeFallback(tg, top)

  setCssVar('--tg-safe-top', `${safeTop}px`)
  setCssVar('--tg-safe-bottom', `${safeBottom}px`)
  setCssVar('--tg-safe-left', `${left}px`)
  setCssVar('--tg-safe-right', `${right}px`)
  setCssVar('--tg-content-top', `${Math.round(top)}px`)
  setCssVar('--tg-content-bottom', `${Math.round(bottom)}px`)

  document.documentElement.dataset.tgViewport = '1'
  document.documentElement.dataset.tgInsetTop = String(Math.round(top))
  document.documentElement.classList.toggle('tg-fullscreen', Boolean(tg.isFullscreen))
  document.documentElement.classList.toggle('tg-webapp', true)
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
    // older clients
  }

  window.addEventListener('resize', sync)
  window.visualViewport?.addEventListener?.('resize', sync)
}

function applyTelegramViewport(tg) {
  if (!tg) return
  const desktop = isDesktopTelegram(tg)

  try {
    tg.expand()
  } catch {
    /* ignore */
  }

  if (desktop) {
    if (tg.isFullscreen && typeof tg.exitFullscreen === 'function') {
      try {
        tg.exitFullscreen()
      } catch {
        /* ignore */
      }
    }
  } else if (typeof tg.requestFullscreen === 'function' && !tg.isFullscreen) {
    try {
      tg.requestFullscreen()
    } catch {
      /* ignore */
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
    return null
  }

  tg.ready()

  const desktop = isDesktopTelegram(tg)
  document.documentElement.dataset.tgDesktop = desktop ? '1' : '0'
  document.documentElement.dataset.tgPlatform = String(tg.platform || 'unknown')

  try {
    // Тот же тон, что panel-shell — зона под полупрозрачной шапкой TG выглядит цельно
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

  applyTelegramViewport(tg)
  requestAnimationFrame(() => applyTelegramViewport(tg))
  window.setTimeout(() => applyTelegramViewport(tg), 80)
  window.setTimeout(() => applyTelegramViewport(tg), 200)
  if (!desktop) {
    window.setTimeout(() => applyTelegramViewport(tg), 450)
    window.setTimeout(() => applyTelegramViewport(tg), 1200)
  }

  bindViewportSync(tg)
  return tg
}

export function getTelegramUser() {
  const user = window.Telegram?.WebApp?.initDataUnsafe?.user
  if (!user?.id) return null
  return user
}
