/** Срок наказания в секундах. Короче 35 секунд Telegram считает вечным. */

export const SPAN_FLOOR_SEC = 35
export const SPAN_MAX_SEC = 366 * 24 * 3600

export const SPAN_PRESETS = [
  { id: '5m', label: '5 мин', sec: 5 * 60 },
  { id: '1h', label: '1 час', sec: 3600 },
  { id: '12h', label: '12 ч', sec: 12 * 3600 },
  { id: '1d', label: '1 день', sec: 86400 },
  { id: '7d', label: '7 дней', sec: 7 * 86400 },
]

function asCount(value) {
  const number = Math.floor(Number(String(value ?? '').replace(/\D/g, '')) || 0)
  return number > 0 ? number : 0
}

export function splitSpan(total) {
  let rest = Math.max(0, Math.floor(Number(total) || 0))
  const days = Math.floor(rest / 86400)
  rest -= days * 86400
  const hours = Math.floor(rest / 3600)
  rest -= hours * 3600
  const minutes = Math.floor(rest / 60)
  rest -= minutes * 60
  return { days, hours, minutes, seconds: rest }
}

export function sumSpan(parts) {
  const row = parts || {}
  return asCount(row.days) * 86400
    + asCount(row.hours) * 3600
    + asCount(row.minutes) * 60
    + asCount(row.seconds)
}

export function carrySpan(parts) {
  let seconds = asCount(parts?.seconds)
  let minutes = asCount(parts?.minutes) + Math.floor(seconds / 60)
  seconds %= 60
  let hours = asCount(parts?.hours) + Math.floor(minutes / 60)
  minutes %= 60
  let days = asCount(parts?.days) + Math.floor(hours / 24)
  hours %= 24
  let total = days * 86400 + hours * 3600 + minutes * 60 + seconds
  if (total > SPAN_MAX_SEC) {
    return { ...splitSpan(SPAN_MAX_SEC), total: SPAN_MAX_SEC, capped: true }
  }
  return { days, hours, minutes, seconds, total, capped: false }
}

export function spanToSend(total) {
  const number = Math.floor(Number(total) || 0)
  if (number <= 0 || number > SPAN_MAX_SEC) return null
  return Math.max(SPAN_FLOOR_SEC, number)
}

export function ruCount(value, one, few, many) {
  const abs = Math.abs(Math.floor(Number(value) || 0))
  const tail = abs % 10
  const hundred = abs % 100
  const word = tail === 1 && hundred !== 11
    ? one
    : tail >= 2 && tail <= 4 && (hundred < 12 || hundred > 14)
      ? few
      : many
  return `${abs} ${word}`
}

export function speakSpan(total) {
  const number = Math.floor(Number(total) || 0)
  if (number <= 0) return ''
  const parts = splitSpan(number)
  const bits = []
  if (parts.days) bits.push(ruCount(parts.days, 'день', 'дня', 'дней'))
  if (parts.hours) bits.push(ruCount(parts.hours, 'час', 'часа', 'часов'))
  if (parts.minutes) bits.push(ruCount(parts.minutes, 'минута', 'минуты', 'минут'))
  if (parts.seconds) bits.push(ruCount(parts.seconds, 'секунда', 'секунды', 'секунд'))
  return bits.join(' ')
}
