/** Должности, на которые можно посадить человека из заявки или с доски. */

export function adminSeatChoices(groups, options = {}) {
  const includeSpamblock = Boolean(options.includeSpamblock)
  return (groups || []).map((group) => {
    const posts = (group.positions || []).filter((post) => {
      const kind = post.kind || 'post'
      const rank = Number(post.rank)
      if (!Number.isFinite(rank) || rank >= 5) return false
      if (kind === 'post') return true
      if (includeSpamblock && kind === 'spamblock') return true
      return false
    })
    return {
      chatId: group.chatId,
      title: group.title || String(group.chatId),
      posts,
    }
  })
}

export function typedChatId(query) {
  const text = String(query || '').trim()
  if (!/^-?\d{6,}$/.test(text)) return null
  const id = Number(text)
  return Number.isSafeInteger(id) ? id : null
}

export function positionKindLabel(kind) {
  if (kind === 'spamblock') return 'Спам-блок'
  if (kind === 'member') return 'Участник'
  return 'Админ'
}

/** Соседние должности для быстрого повышения / понижения в одной группе. */
export function rankNeighbors(group, seat) {
  if (!group || !seat) return { up: null, down: null, ladder: [] }
  if (seat.kind === 'spamblock' || seat.kind === 'member') {
    return { up: null, down: null, ladder: [] }
  }
  const ladder = (group.positions || [])
    .filter((post) => {
      const kind = post.kind || 'post'
      const rank = Number(post.rank)
      return kind === 'post' && Number.isFinite(rank) && rank < 5
    })
    .slice()
    .sort((a, b) => {
      const rankDiff = Number(a.rank) - Number(b.rank)
      if (rankDiff !== 0) return rankDiff
      return Number(a.id) - Number(b.id)
    })
  const currentId = Number(seat.positionId)
  let index = ladder.findIndex((post) => Number(post.id) === currentId)
  if (index < 0) {
    index = ladder.findIndex((post) => String(post.title) === String(seat.position || ''))
  }
  if (index < 0) return { up: null, down: null, ladder }
  return {
    up: ladder[index + 1] || null,
    down: ladder[index - 1] || null,
    ladder,
  }
}
