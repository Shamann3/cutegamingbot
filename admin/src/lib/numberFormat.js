const FULL = new Intl.NumberFormat('ru-RU')

export function fmt(n) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  return FULL.format(Number(n))
}

const COMPACT_STEPS = [
  { at: 1e12, unit: 'трлн' },
  { at: 1e9, unit: 'млрд' },
  { at: 1e6, unit: 'млн' },
  { at: 1e3, unit: 'тыс' },
]

/** Короткая запись — чтобы миллионные суммы не распирали карточку. */
export function fmtCompact(n) {
  if (n == null) return '—'
  const value = Number(n)
  if (!Number.isFinite(value)) return '—'
  const abs = Math.abs(value)
  const index = COMPACT_STEPS.findIndex((item) => abs >= item.at)
  if (index === -1) return FULL.format(value)
  let step = COMPACT_STEPS[index]
  let scaled = value / step.at
  // 999 950 не должно превращаться в «1 000 тыс» — переходим на следующий шаг.
  if (Math.abs(Math.round(scaled * 10) / 10) >= 1000 && index > 0) {
    step = COMPACT_STEPS[index - 1]
    scaled = value / step.at
  }
  const digits = Math.abs(scaled) >= 100 ? 0 : 1
  const text = new Intl.NumberFormat('ru-RU', {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  }).format(scaled)
  return `${text} ${step.unit}`
}
