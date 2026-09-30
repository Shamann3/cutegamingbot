/** Имя на карточке заявки: как человек подписан, затем @username. */
export function applicationPerson(item) {
  const name = String(item?.name || item?.firstName || '').trim()
  const username = String(item?.username || '').replace(/^@/, '').trim()
  if (name) return { title: name, username }
  if (username) return { title: `@${username}`, username: '' }
  return { title: 'Имя не найдено', username: '' }
}
