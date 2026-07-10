export const DONATE_BOT_USERNAME = import.meta.env.VITE_DONATE_BOT_USERNAME || 'CuteGamingBot'

export const DONATE_MIN_AMOUNT = 1
export const DONATE_MAX_AMOUNT = 99_999
export const DONATE_DEFAULT_AMOUNT = 100

export const DONATE_PRESETS = [100, 500, 1000]

/** Суффикс deep link. В start Telegram разрешены только A-Z, a-z, 0-9, _ и -. */
const DONATE_START_SUFFIX = (import.meta.env.VITE_DONATE_START_SUFFIX || '_').replace(/[^A-Za-z0-9_-]/g, '')

export function buildDonateStartPayload(amount) {
  const value = Math.max(DONATE_MIN_AMOUNT, Math.min(DONATE_MAX_AMOUNT, Math.floor(amount)))
  return `insert_${value}${DONATE_START_SUFFIX}`
}

export function buildDonateBotUrl(amount) {
  const username = DONATE_BOT_USERNAME.replace(/^@/, '')
  const payload = buildDonateStartPayload(amount)
  return `https://t.me/${username}?start=${payload}`
}

export const DONATE_DISCLAIMER = {
  title: 'Конфиденциальность',
  lines: [
    'Ваши данные обрабатываются конфиденциально и не передаются третьим лицам.',
    'Мы не видим и не храним данные ваших карт - платежи идут через защищённые сервисы.',
    'Администрация не несёт ответственности за задержки зачислений, сбои платежей или действия сторонних сервисов (включая Telegram).',
    'Если возникла проблема - напишите в поддержку, мы поможем разобраться.',
  ],
}