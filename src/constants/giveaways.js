// Переключатель заглушки «скоро»: true — вкладка «Розыгрыши» показывает
// только анонс-плашку вместо реального списка; false — обычный интерфейс.
export const GIVEAWAYS_COMING_SOON = false

export const RARITY_ORDER = ['common', 'rare', 'legendary']

export const RARITY_LABEL = {
  common: 'Обычный',
  rare: 'Редкий',
  legendary: 'Легендарный',
}

// Свечение по редкости: обычный — зелёный, редкий — голубой, легендарный —
// золотой (с искрами в карточке). soft — приглушённый тон для подложек.
export const RARITY_ACCENT = {
  common: { strong: '#34d399', glow: 'rgba(52, 211, 153, 0.34)', soft: 'rgba(52, 211, 153, 0.12)' },
  rare: { strong: '#5b9be0', glow: 'rgba(91, 155, 224, 0.34)', soft: 'rgba(91, 155, 224, 0.12)' },
  legendary: { strong: '#f7c948', glow: 'rgba(247, 201, 72, 0.40)', soft: 'rgba(247, 201, 72, 0.12)' },
}

export function formatGiveawayDeadline(endsAtIso) {
  if (!endsAtIso) return null
  return new Date(endsAtIso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })
}

export function formatGiveawayDeadlineTime(endsAtIso) {
  if (!endsAtIso) return null
  const date = new Date(endsAtIso)
  const day = date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })
  const time = date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  return `${day} в ${time}`
}

// Живой обратный отсчёт: «2 дн 14 ч» / «14 ч 32 мин» / «32 мин 10 с» / «12 с».
// Аббревиатуры (дн/ч/мин/с) — чтобы не мучиться со склонениями и держать
// компактность. Возвращает null, когда время вышло.
export function formatCountdown(targetIso, now = Date.now()) {
  if (!targetIso) return null
  const diff = new Date(targetIso).getTime() - now
  if (diff <= 0) return null
  const totalSec = Math.floor(diff / 1000)
  const days = Math.floor(totalSec / 86400)
  const hours = Math.floor((totalSec % 86400) / 3600)
  const mins = Math.floor((totalSec % 3600) / 60)
  const secs = totalSec % 60
  if (days >= 1) return `${days} дн ${hours} ч`
  if (hours >= 1) return `${hours} ч ${mins} мин`
  if (mins >= 1) return `${mins} мин ${secs} с`
  return `${secs} с`
}

// Осталось меньше суток (для «горящего» состояния таймера/бейджа).
export function isEndingSoon(targetIso, now = Date.now()) {
  if (!targetIso) return false
  const diff = new Date(targetIso).getTime() - now
  return diff > 0 && diff <= 24 * 3600 * 1000
}

// Розыгрыш проходит сегодня (по календарной дате).
export function isDrawToday(targetIso, now = Date.now()) {
  if (!targetIso) return false
  const t = new Date(targetIso)
  const n = new Date(now)
  return t.getFullYear() === n.getFullYear()
    && t.getMonth() === n.getMonth()
    && t.getDate() === n.getDate()
    && t.getTime() >= now
}

export function formatGiveawayPrize(prize) {
  if (!prize) return ''
  if (prize.type === 'kut') return `${Number(prize.amount ?? 0).toLocaleString('ru-RU')} КУТ`
  return `${prize.emoji ?? '🎁'} ${prize.title ?? 'Приз'}`
}
