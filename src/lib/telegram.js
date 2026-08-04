/**
 * Telegram Mini App: auth + viewport / safe-area sync.
 * ПК — обычный размер панели (без requestFullscreen), как дефолт Telegram.
 */

function setCssVar(name, value) {
  document.documentElement.style.setProperty(name, value)
}

function syncTelegramViewport(tg) {
  if (!tg) return

  const h = Number(tg.viewportStableHeight || tg.viewportHeight || window.innerHeight) || window.innerHeight
  setCssVar('--app-vh', `${Math.round(h)}px`)

  const content = tg.contentSafeAreaInset || {}
  const safe = tg.safeAreaInset || {}

  const top = Number(content.top ?? safe.top ?? 0) || 0
  const bottom = Number(content.bottom ?? safe.bottom ?? 0) || 0
  const left = Number(content.left ?? safe.left ?? 0) || 0
  const right = Number(content.right ?? safe.right ?? 0) || 0

  setCssVar('--tg-safe-top', `${top}px`)
  setCssVar('--tg-safe-bottom', `${bottom}px`)
  setCssVar('--tg-safe-left', `${left}px`)
  setCssVar('--tg-safe-right', `${right}px`)

  document.documentElement.dataset.tgViewport = '1'
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
  window.visualViewport?.addEventListener('resize', sync)
}

export function isDesktopTelegram(tg = window.Telegram?.WebApp) {
  const platform = String(tg?.platform || '').toLowerCase()
  if (platform === 'tdesktop' || platform === 'web' || platform === 'weba' || platform === 'macos' || platform === 'linux' || platform === 'windows') {
    return true
  }
  try {
    const wide = window.innerWidth >= 820
    const fine = window.matchMedia?.('(pointer: fine)').matches
    return wide && fine
  } catch {
    return false
  }
}

function syncFullscreenClass(tg) {
  document.documentElement.classList.toggle('tg-fullscreen', Boolean(tg?.isFullscreen))
}

/**
 * Заполнить доступную панель Mini App.
 * На ПК — только expand (дефолтный размер Telegram), без fullscreen.
 * На телефоне — expand + requestFullscreen для комфортного viewport.
 */
export function applyTelegramViewport(tg = window.Telegram?.WebApp) {
  if (!tg) return

  const desktop = isDesktopTelegram(tg)

  try {
    tg.expand()
  } catch {
    // ignore
  }

  if (desktop) {
    // Вернуть обычный размер, если клиент уже в fullscreen
    if (tg.isFullscreen && typeof tg.exitFullscreen === 'function') {
      try {
        tg.exitFullscreen()
      } catch {
        // ignore
      }
    }
  } else if (typeof tg.requestFullscreen === 'function' && !tg.isFullscreen) {
    try {
      tg.requestFullscreen()
    } catch {
      // not supported / user denied
    }
  }

  syncFullscreenClass(tg)
  syncTelegramViewport(tg)
}

export function initTelegramWebApp() {
  const tg = window.Telegram?.WebApp
  if (!tg) {
    setCssVar('--app-vh', `${window.innerHeight}px`)
    const sync = () => setCssVar('--app-vh', `${window.innerHeight}px`)
    window.addEventListener('resize', sync)
    window.visualViewport?.addEventListener('resize', sync)
    document.documentElement.dataset.tgDesktop = window.innerWidth >= 820 ? '1' : '0'
    return null
  }

  tg.ready()

  const desktop = isDesktopTelegram(tg)
  document.documentElement.dataset.tgDesktop = desktop ? '1' : '0'
  document.documentElement.dataset.tgPlatform = String(tg.platform || 'unknown')

  try {
    tg.disableVerticalSwipes?.()
  } catch {
    // ignore
  }

  try {
    tg.setHeaderColor?.('#050806')
    tg.setBackgroundColor?.('#050806')
  } catch {
    // ignore
  }

  applyTelegramViewport(tg)
  requestAnimationFrame(() => applyTelegramViewport(tg))
  setTimeout(() => applyTelegramViewport(tg), 120)

  // На телефоне иногда fullscreen применяется с задержкой
  if (!desktop) {
    setTimeout(() => applyTelegramViewport(tg), 350)
    setTimeout(() => applyTelegramViewport(tg), 1200)

    try {
      tg.onEvent?.('viewportChanged', () => {
        if (!tg.isFullscreen) applyTelegramViewport(tg)
        else syncTelegramViewport(tg)
      })
    } catch {
      // older clients
    }
  } else {
    // ПК: если пользователь/клиент случайно ушёл в FS — вернуть обычный размер
    try {
      tg.onEvent?.('fullscreenChanged', () => {
        if (tg.isFullscreen) applyTelegramViewport(tg)
        else {
          syncFullscreenClass(tg)
          syncTelegramViewport(tg)
        }
      })
    } catch {
      // ignore
    }
  }

  try {
    tg.onEvent?.('fullscreenChanged', () => {
      syncFullscreenClass(tg)
      syncTelegramViewport(tg)
    })
  } catch {
    // ignore
  }

  if (tg.themeParams?.bg_color) {
    setCssVar('--tg-bg', tg.themeParams.bg_color)
  }

  bindViewportSync(tg)
  return tg
}

/** Синхронизация viewport при входе / смене экрана. */
export function ensureTelegramFullscreen() {
  applyTelegramViewport()
}

export function isTelegramWebApp() {
  return Boolean(window.Telegram?.WebApp?.initData)
}

export function getTelegramUser() {
  const user = window.Telegram?.WebApp?.initDataUnsafe?.user
  if (!user?.id) return null
  return user
}

export function getTelegramInitData() {
  return window.Telegram?.WebApp?.initData ?? ''
}

export function canAuthenticate() {
  if (getTelegramInitData()) return true
  if (import.meta.env.DEV && import.meta.env.VITE_DEV_USER_ID) return true
  return false
}

export function getAuthErrorMessage() {
  if (isTelegramWebApp() && !getTelegramInitData()) {
    return 'Telegram не передал данные. Пожалуйста, закройте и откройте ферму через бота.'
  }
  if (!isTelegramWebApp() && !import.meta.env.DEV) {
    return 'Пожалуйста, откройте ферму через Telegram бота (кнопка в чате).'
  }
  if (import.meta.env.DEV && !import.meta.env.VITE_DEV_USER_ID) {
    return 'Локальный тест: задайте VITE_DEV_USER_ID в .env или откройте через Telegram.'
  }
  return 'Не удалось определить пользователя.'
}

const VALID_TABS = new Set(['farm', 'inventory', 'craft', 'quests', 'shop', 'market', 'trade', 'giveaways', 'settings'])

export function getStartTab() {
  const tg = window.Telegram?.WebApp
  const param = tg?.initDataUnsafe?.start_param ?? ''
  return VALID_TABS.has(param) ? param : null
}

export function openTelegramBotLink(url) {
  const tg = window.Telegram?.WebApp
  const href = String(url || '').trim()
  if (!href) return false

  if (href.startsWith('https://t.me/') && tg?.openTelegramLink) {
    tg.openTelegramLink(href)
    return true
  }
  if (tg?.openLink) {
    tg.openLink(href, { try_instant_view: false })
    return true
  }
  window.location.assign(href)
  return true
}
