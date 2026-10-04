/** Курс бота: 1 кут = 1 звезда. $0.013 — сколько остаётся за звезду после 30% Telegram. */
export const STAR_NET_USD = 0.013
export const TELEGRAM_FEE = 0.3

const COUNTS = {
  Баны: ['бан', 'бана', 'банов'],
  Муты: ['мут', 'мута', 'мутов'],
  Кики: ['кик', 'кика', 'киков'],
  Предупреждения: ['предупреждение', 'предупреждения', 'предупреждений'],
  'Проверки администраторов': ['проверка', 'проверки', 'проверок'],
  'Проверки сотрудников': ['проверка', 'проверки', 'проверок'],
}

export function countPhrase(n, title) {
  const num = Math.max(0, Math.round(Number(n) || 0))
  const forms = COUNTS[title]
  if (!forms) return `${num} дел «${title}»`
  const n10 = num % 10
  const n100 = num % 100
  let form = forms[2]
  if (n10 === 1 && n100 !== 11) form = forms[0]
  else if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) form = forms[1]
  return `${num} ${form}`
}

export function starWords(n) {
  const num = Math.max(0, Math.round(Number(n) || 0))
  const n10 = num % 10
  const n100 = num % 100
  let form = 'звёзд'
  if (n10 === 1 && n100 !== 11) form = 'звезда'
  else if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) form = 'звезды'
  return `${num.toLocaleString('ru-RU')} ${form}`
}

export function kutQuote(raw) {
  const text = String(raw ?? '').trim().replace(',', '.')
  const kut = Math.max(0, Number(text) || 0)
  const stars = kut
  const netUsd = stars * STAR_NET_USD
  const grossUsd = TELEGRAM_FEE >= 1 ? netUsd : netUsd / (1 - TELEGRAM_FEE)
  return { kut, stars, netUsd, grossUsd, fee: TELEGRAM_FEE }
}

export function formatUsd(value) {
  const abs = Math.abs(Number(value) || 0)
  const digits = abs !== 0 && abs < 0.1 ? 3 : 2
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(Number(value) || 0)
}

export function formatKut(value) {
  return `${Number(value || 0).toLocaleString('ru-RU')} кут`
}
