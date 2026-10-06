/** Должности, на которые создатель может посадить человека из заявки. */

export function adminSeatChoices(groups) {
  return (groups || []).map((group) => {
    const posts = (group.positions || []).filter((post) => {
      const kind = post.kind || 'post'
      return kind === 'post' && Number(post.rank) < 5
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
