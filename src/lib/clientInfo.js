/** Данные клиента WebApp для отправки на сервер. */

function parseDeviceModel(userAgent) {
  if (!userAgent) return null
  const android = userAgent.match(/;\s*([^;)]+)\s+Build\//i)
  if (android?.[1]) return android[1].trim().slice(0, 120)
  const ios = userAgent.match(/\((iPhone[^)]+)\)/i)
  if (ios?.[1]) return ios[1].trim().slice(0, 120)
  if (/iPad/i.test(userAgent)) return 'iPad'
  if (/Macintosh/i.test(userAgent) && /Mobile/i.test(userAgent)) return 'iPhone/iPad (WebKit)'
  return null
}

export function collectClientInfo() {
  const tg = window.Telegram?.WebApp
  const tgUser = tg?.initDataUnsafe?.user
  const userAgent = typeof navigator !== 'undefined' ? navigator.userAgent?.slice(0, 500) : null

  return {
    platform: tg?.platform || null,
    tgPlatform: tg?.platform || null,
    appVersion: tg?.version || null,
    userAgent,
    language: tgUser?.language_code || null,
    isPremium: tgUser?.is_premium ?? null,
    navigatorLanguage: typeof navigator !== 'undefined' ? navigator.language : null,
    timezone: typeof Intl !== 'undefined'
      ? Intl.DateTimeFormat().resolvedOptions().timeZone
      : null,
    colorScheme: tg?.colorScheme || null,
    deviceModel: parseDeviceModel(userAgent),
    viewportWidth: tg?.viewportWidth ?? (typeof window !== 'undefined' ? window.innerWidth : null),
    viewportHeight: tg?.viewportHeight ?? (typeof window !== 'undefined' ? window.innerHeight : null),
    screenWidth: typeof screen !== 'undefined' ? screen.width : null,
    screenHeight: typeof screen !== 'undefined' ? screen.height : null,
    isExpanded: tg?.isExpanded ?? null,
  }
}

export function getClientInfoHeaders() {
  const info = collectClientInfo()
  const filtered = Object.fromEntries(
    Object.entries(info).filter(([, value]) => value != null && value !== ''),
  )
  if (!Object.keys(filtered).length) return {}

  try {
    const json = JSON.stringify(filtered)
    const b64 = btoa(unescape(encodeURIComponent(json)))
    return { 'X-Client-Info': b64 }
  } catch {
    return {}
  }
}
