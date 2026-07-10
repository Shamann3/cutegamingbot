/** Парсит целое из поля формы; пустая строка → undefined (не менять на сервере). */
export function parseOptionalInt(value) {
  const trimmed = String(value ?? '').trim()
  if (!trimmed) return undefined
  const parsed = Number.parseInt(trimmed, 10)
  return Number.isFinite(parsed) ? parsed : undefined
}

/** Собирает объект настроек только с заполненными числовыми полями. */
export function pickOptionalIntFields(fields) {
  const payload = {}
  for (const [key, value] of Object.entries(fields)) {
    const parsed = parseOptionalInt(value)
    if (parsed !== undefined) payload[key] = parsed
  }
  return payload
}

/** Все поля обязательны для форм «Сохранить настройки». */
export function parseRequiredIntFields(fields, labels = {}) {
  const payload = {}
  for (const [key, value] of Object.entries(fields)) {
    const parsed = parseOptionalInt(value)
    if (parsed === undefined) {
      throw new Error(`Заполните поле: ${labels[key] ?? key}`)
    }
    payload[key] = parsed
  }
  return payload
}
