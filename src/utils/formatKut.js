export function formatKut(value) {
  return Number(value ?? 0).toLocaleString('ru-RU').replace(/\s/g, '.')
}
