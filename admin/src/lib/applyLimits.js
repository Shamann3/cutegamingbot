/** Длина текста заявки. Та же граница на сервере: 50 и 2000. */

export const APPLY_MIN = 50
export const APPLY_MAX = 2000

export function applyLength(value) {
  return String(value || '').trim().length
}

export function symbolsWord(count) {
  const mod10 = count % 10
  const mod100 = count % 100
  if (mod10 === 1 && mod100 !== 11) return 'символ'
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'символа'
  return 'символов'
}

export function applyHint(value, optional = false) {
  const length = applyLength(value)
  if (length > APPLY_MAX) {
    const over = length - APPLY_MAX
    return `Слишком длинно: уберите ${over} ${symbolsWord(over)}. Можно не больше ${APPLY_MAX}.`
  }
  if (length === 0) {
    return optional
      ? `Можно не писать. Если пишете — от ${APPLY_MIN} до ${APPLY_MAX} символов`
      : `От ${APPLY_MIN} до ${APPLY_MAX} символов`
  }
  if (length < APPLY_MIN) return `Ещё ${APPLY_MIN - length} ${symbolsWord(APPLY_MIN - length)}`
  return `${length} из ${APPLY_MAX} символов`
}

export function applyReady(value) {
  const length = applyLength(value)
  return length >= APPLY_MIN && length <= APPLY_MAX
}
