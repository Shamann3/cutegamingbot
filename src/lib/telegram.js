/**
 * Telegram Mini App: auth + viewport / fullscreen / safe-area sync.
 */

function setCssVar(name, value) {
  document.documentElement.style.setProperty(name, value)
}

function syncTelegramViewport(tg) {
  if (!tg) return

  const h = Number(tg.viewportStableHeight || tg.viewportHeight || window.innerHeight) || window.innerHeight
  setCssVar('--app-vh', `${Math.round(h)}px`)

  // contentSafeAreaInset учитывает кнопки Telegram (✕ / ⋯)
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

  // CSS env() fallbacks still work; these override when TG reports insets
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

export function initTelegramWebApp() {
  const tg = window.Telegram?.WebApp
  if (!tg) {
    // Browser / preview: fill window
    setCssVar('--app-vh', `${window.innerHeight}px`)
    const sync = () => setCssVar('--app-vh', `${window.innerHeight}px`)
    window.addEventListener('resize', sync)
    window.visualViewport?.addEventListener('resize', sync)
    return null
  }

  tg.ready()
  tg.expand()

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

  const requestFull = () => {
    try {
      tg.expand()
      if (typeof tg.requestFullscreen === 'function' && !tg.isFullscreen) {
        tg.requestFullscreen()
      }
    } catch {
      // not supported / user denied
    }
    syncTelegramViewport(tg)
  }

  // Bot API 8+: fullscreen; повтор через кадр — клиент иногда не готов сразу
  requestFull()
  requestAnimationFrame(requestFull)
  setTimeout(requestFull, 350)
  setTimeout(requestFull, 1200)

  if (tg.themeParams?.bg_color) {
    setCssVar('--tg-bg', tg.themeParams.bg_color)
  }

  bindViewportSync(tg)
  return tg
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

/** Готовы ли заголовки для запросов к серверу */
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

/** Читает вкладку из startapp-параметра Telegram (например ?startapp=market) */
export function getStartTab() {
  const tg = window.Telegram?.WebApp
  const param = tg?.initDataUnsafe?.start_param ?? ''
  return VALID_TABS.has(param) ? param : null
}

/** Открывает t.me / tg:// ссылку (чат с ботом или личка с пользователем). */
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
