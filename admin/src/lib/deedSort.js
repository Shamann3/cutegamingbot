export const SORT_LABEL = {
  clear: 'Подходит',
  wrong: 'Не подходит',
  weak: 'Непонятно',
}

export const BAND_LABEL = {
  photo: 'Есть фото',
  reason: 'Фото нет, есть причина',
  empty: 'Ни фото, ни причины',
}

export function sortLabel(verdict) {
  return SORT_LABEL[verdict] || ''
}

export function sortCountLine(counts) {
  const clear = Number(counts?.clear) || 0
  const wrong = Number(counts?.wrong) || 0
  const weak = Number(counts?.weak) || 0
  return `Подходит ${clear}. Не подходит ${wrong}. Непонятно ${weak}.`
}

export function payLabel(status) {
  if (status === 'kept') return 'В зарплате'
  if (status === 'dropped') return 'Не в зарплате'
  return ''
}

/** Кто проверял: «Анна: подходит», «Не смогли решить: Анна, Олег», «Некому было проверить». */
export function checkedBy(item) {
  const names = (item?.unclearNames || []).filter(Boolean)
  const precise = item?.sortVerdict && item.sortVerdict !== 'weak'
  if (precise) {
    const head = `${item.sorterName || 'Администратор'}: ${sortLabel(item.sortVerdict).toLowerCase()}`
    return names.length ? `${head} · до этого не смогли решить: ${names.join(', ')}` : head
  }
  if (names.length) return `Не смогли решить: ${names.join(', ')}`
  if (item?.sortVerdict === 'weak') return 'Не смогли решить'
  return 'Некому было проверить'
}

export function admins(n) {
  const num = Math.abs(Number(n) || 0)
  const n10 = num % 10
  const n100 = num % 100
  if (n10 === 1 && n100 !== 11) return `${num} администратор`
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) return `${num} администратора`
  return `${num} администраторов`
}

export function punishments(n) {
  const num = Math.abs(Number(n) || 0)
  const n10 = num % 10
  const n100 = num % 100
  if (n10 === 1 && n100 !== 11) return 'наказание'
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) return 'наказания'
  return 'наказаний'
}

/** «наказание ждёт вашей проверки», «наказания ждут вашего решения». */
export function waitCaption(n, tail) {
  const num = Math.abs(Number(n) || 0)
  const one = num % 10 === 1 && num % 100 !== 11
  return `${punishments(num)} ${one ? 'ждёт' : 'ждут'} ${tail}`
}
