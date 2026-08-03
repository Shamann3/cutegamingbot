/** Склонение: 1 день, 2 дня, 5 дней */
function pluralRu(n, one, few, many) {
  const abs = Math.abs(n) % 100
  const last = abs % 10
  if (abs > 10 && abs < 20) return many
  if (last === 1) return one
  if (last >= 2 && last <= 4) return few
  return many
}

/**
 * Короткий понятный отсчёт для карточки грядки.
 * Примеры: «5 д 3 ч», «2 ч 15 мин», «45 сек», «1 мес 12 д»
 */
export function formatDurationRu(ms) {
  if (!Number.isFinite(ms) || ms <= 0) return 'готово'

  const totalSec = Math.max(0, Math.ceil(ms / 1000))
  const years = Math.floor(totalSec / (365 * 24 * 3600))
  let rem = totalSec % (365 * 24 * 3600)
  const months = Math.floor(rem / (30 * 24 * 3600))
  rem %= 30 * 24 * 3600
  const days = Math.floor(rem / (24 * 3600))
  rem %= 24 * 3600
  const hours = Math.floor(rem / 3600)
  rem %= 3600
  const minutes = Math.floor(rem / 60)
  const seconds = rem % 60

  const parts = []

  if (years > 0) parts.push(`${years} г.`)
  if (months > 0) parts.push(`${months} мес.`)
  if (days > 0) parts.push(`${days} д.`)

  if (parts.length < 3 && (years === 0 || hours > 0) && hours > 0) {
    parts.push(`${hours} ч.`)
  }

  if (parts.length < 3 && years === 0 && months === 0 && minutes > 0) {
    parts.push(`${minutes} мин.`)
  }

  if (parts.length === 0) {
    return `${seconds} сек.`
  }

  // Меньше часа — добавим секунды для точности
  if (
    parts.length < 3
    && years === 0
    && months === 0
    && days === 0
    && hours === 0
    && minutes > 0
    && seconds > 0
  ) {
    parts.push(`${seconds} сек.`)
  }

  return parts.slice(0, 3).join(' ')
}

/** Полная форма: «2 дня 5 часов 12 минут» */
export function formatDurationRuLong(ms) {
  if (!Number.isFinite(ms) || ms <= 0) return 'готово'

  const totalSec = Math.max(0, Math.ceil(ms / 1000))
  const years = Math.floor(totalSec / (365 * 24 * 3600))
  let rem = totalSec % (365 * 24 * 3600)
  const months = Math.floor(rem / (30 * 24 * 3600))
  rem %= 30 * 24 * 3600
  const days = Math.floor(rem / (24 * 3600))
  rem %= 24 * 3600
  const hours = Math.floor(rem / 3600)
  rem %= 3600
  const minutes = Math.floor(rem / 60)
  const seconds = rem % 60

  const parts = []
  if (years > 0) parts.push(`${years} ${pluralRu(years, 'год', 'года', 'лет')}`)
  if (months > 0) parts.push(`${months} ${pluralRu(months, 'месяц', 'месяца', 'месяцев')}`)
  if (days > 0) parts.push(`${days} ${pluralRu(days, 'день', 'дня', 'дней')}`)
  if (hours > 0) parts.push(`${hours} ${pluralRu(hours, 'час', 'часа', 'часов')}`)
  if (minutes > 0 && years === 0 && months === 0) {
    parts.push(`${minutes} ${pluralRu(minutes, 'минута', 'минуты', 'минут')}`)
  }
  if (
    parts.length === 0
    || (years === 0 && months === 0 && days === 0 && hours === 0 && (minutes === 0 || seconds > 0))
  ) {
    if (minutes === 0 || (days === 0 && hours === 0 && seconds > 0)) {
      // избегаем дубля секунд
      const hasSec = parts.some((p) => p.includes('сек'))
      if (!hasSec) {
        parts.push(`${seconds} ${pluralRu(seconds, 'секунда', 'секунды', 'секунд')}`)
      }
    }
  }

  return parts.slice(0, 4).join(' ')
}
