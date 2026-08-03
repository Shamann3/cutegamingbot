/**
 * Telegram Mini App user_id и initData приходят автоматически из Telegram.
 * Ничего вручную в .env для обычного запуска не нужно.
 */

export function initTelegramWebApp() {
  const tg = window.Telegram?.WebApp
  if (!tg) return null

  tg.ready()
  tg.expand()

  if (tg.themeParams?.bg_color) {
    document.documentElement.style.setProperty('--tg-bg', tg.themeParams.bg_color)
  }

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

  // openTelegramLink принимает только https://t.me/...
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
