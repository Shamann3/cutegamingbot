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
