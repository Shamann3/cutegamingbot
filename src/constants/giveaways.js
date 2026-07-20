// Переключатель заглушки «скоро»: true — вкладка «Розыгрыши» показывает
// только анонс-плашку вместо реального списка; false — обычный интерфейс.
export const GIVEAWAYS_COMING_SOON = true

export const RARITY_ORDER = ['common', 'rare', 'legendary']

export const RARITY_LABEL = {
  common: 'Обычный',
  rare: 'Редкий',
  legendary: 'Легендарный',
}

// legendary переиспользует тот же розово-золотой акцент, что уже задан
// для самой вкладки «Розыгрыши» в src/styles/tabThemes.css (--tab-accent-strong).
export const RARITY_ACCENT = {
  common: { strong: '#34d399', glow: 'rgba(52, 211, 153, 0.32)' },
  rare: { strong: '#5b9be0', glow: 'rgba(91, 155, 224, 0.32)' },
  legendary: { strong: '#f472b6', glow: 'rgba(244, 114, 182, 0.34)' },
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

export function formatGiveawayPrize(prize) {
  if (!prize) return ''
  if (prize.type === 'kut') return `${Number(prize.amount ?? 0).toLocaleString('ru-RU')} КУТ`
  return `${prize.emoji ?? '🎁'} ${prize.title ?? 'Приз'}`
}
