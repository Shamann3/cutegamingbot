/**
 * Telegram Mini App viewport + safe-area для admin-панели.
 * Без --tg-safe-* шапка Telegram (✕ / меню) наезжает на контент.
 */

function setCssVar(name, value) {
  document.documentElement.style.setProperty(name, value)
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

  // contentSafeArea — зона под UI Telegram; safeArea — вырез/Dynamic Island.
  // Берём максимум по каждой стороне, чтобы покрыть оба слоя.
  const top = Math.max(Number(content.top) || 0, Number(safe.top) || 0)
  const bottom = Math.max(Number(content.bottom) || 0, Number(safe.bottom) || 0)
  const left = Math.max(Number(content.left) || 0, Number(safe.left) || 0)
  const right = Math.max(Number(content.right) || 0, Number(safe.right) || 0)

  setCssVar('--tg-safe-top', `${top}px`)
  setCssVar('--tg-safe-bottom', `${bottom}px`)
  setCssVar('--tg-safe-left', `${left}px`)
  setCssVar('--tg-safe-right', `${right}px`)

  // Сумма для редких клиентов, где content и safe нужно складывать
  const topSum = (Number(content.top) || 0) + (Number(safe.top) || 0)
  const bottomSum = (Number(content.bottom) || 0) + (Number(safe.bottom) || 0)
  setCssVar('--tg-content-top', `${Math.max(top, topSum)}px`)
  setCssVar('--tg-content-bottom', `${Math.max(bottom, bottomSum)}px`)

  document.documentElement.dataset.tgViewport = '1'
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
  window.setTimeout(() => applyTelegramViewport(tg), 120)
  if (!desktop) {
    window.setTimeout(() => applyTelegramViewport(tg), 350)
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
