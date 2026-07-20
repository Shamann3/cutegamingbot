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
