const KINDS = new Set(['post', 'member', 'spamblock'])

function cleanName(value) {
  return String(value || '').trim().replace(/\s+/g, ' ').toLowerCase()
}

/** Почему должность нельзя поставить в эту группу. Пустая строка — можно. */
export function placeBlock({ title, kind, rank, targetTitles, targetKinds }) {
  if (Number(rank) >= 5) return 'Создатель группы уже есть в каждой группе и не копируется'
  const name = cleanName(title)
  if (!name) return 'У должности нет названия'
  const have = new Set((targetTitles || []).map(cleanName))
  if (have.has(name)) return 'Должность с таким названием уже есть'
  const stored = KINDS.has(kind) ? kind : 'post'
  const kinds = new Set(targetKinds || [])
  if (stored === 'member' && kinds.has('member')) return 'Обычный пользователь в этой группе уже есть'
  if (stored === 'spamblock' && kinds.has('spamblock')) return 'Спам-блок в этой группе уже есть'
  return ''
}

export function supplyNotice(data, verb) {
  const placed = (data?.placed || []).map((item) => item.title).filter(Boolean)
  const skipped = data?.skipped || []
  const parts = []
  if (placed.length === 1) parts.push(`${verb} «${placed[0]}»`)
  else if (placed.length) parts.push(`${verb}: ${placed.join(', ')}`)
  if (skipped.length) {
    parts.push(skipped.map((item) => `${item.title}: ${item.reason}`).join('. '))
  }
  return parts.join('. ')
}
