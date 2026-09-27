/** Сравнение периодов и шкала варнов. Нет цифры — нет цвета и нет вывода. */

export const PUNISH_ACTIONS = new Set(['mute', 'ban', 'kick', 'warn'])
export const WARN_LIMIT = 3

export function compareTone(current, previous) {
  if (current == null || previous == null) return null
  const now = Number(current)
  const prev = Number(previous)
  if (!Number.isFinite(now) || !Number.isFinite(prev)) return null
  if (now > prev) return 'good'
  if (now < prev) return 'bad'
  return 'same'
}

export function watchLevel(warns) {
  const count = Number(warns)
  if (!Number.isFinite(count) || count <= 0) return null
  if (count >= WARN_LIMIT) return 'limit'
  if (count >= 2) return 'close'
  return 'watch'
}

export function watchLine(level, warns) {
  const count = Number(warns) || 0
  if (level === 'limit') return `${count} из ${WARN_LIMIT}. Лимит набран: система банит на этом шаге.`
  if (level === 'close') return `${count} из ${WARN_LIMIT}. Ещё одно предупреждение — бан в этом чате.`
  if (level === 'watch') return `${count} из ${WARN_LIMIT}. До бана ещё два предупреждения.`
  return ''
}

export function repeatCounts(rows) {
  const counts = new Map()
  for (const row of rows || []) {
    const action = String(row.action || '').toLowerCase()
    if (!PUNISH_ACTIONS.has(action)) continue
    const id = Number(row.target_user_id || row.userId || 0)
    if (!id) continue
    counts.set(id, (counts.get(id) || 0) + 1)
  }
  return counts
}
