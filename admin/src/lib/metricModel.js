/** Высоты столбцов 0–100. Ноль остаётся нулём.
 *  Близкие числа — линейно. Если максимум больше минимума в 8 раз,
 *  шкала логарифмическая: день остаётся виден рядом с годом. */
export function barPercents(values) {
  const nums = values.map((value) => {
    const n = Number(value)
    return Number.isFinite(n) && n > 0 ? n : 0
  })
  const positive = nums.filter((n) => n > 0)
  if (!positive.length) return nums.map(() => 0)
  const max = Math.max(...positive)
  const min = Math.min(...positive)
  if (max / min <= 8) {
    return nums.map((n) => (n > 0 ? Math.round((n / max) * 100) : 0))
  }
  const logs = positive.map((n) => Math.log10(n))
  const logMin = Math.min(...logs)
  const logMax = Math.max(...logs)
  const span = logMax - logMin
  return nums.map((n) => {
    if (n <= 0 || span <= 0) return n > 0 ? 100 : 0
    const t = (Math.log10(n) - logMin) / span
    return Math.round(14 + t * 86)
  })
}

export function metricDelta(current, previous) {
  if (current == null || previous == null || current === '' || previous === '') return null
  const a = Number(current)
  const b = Number(previous)
  if (!Number.isFinite(a) || !Number.isFinite(b)) return null
  return a - b
}
