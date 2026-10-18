import { describe, expect, it } from 'vitest'
import { adminSeatChoices, positionKindLabel, typedChatId } from './seatChoice'

const SAMPLE = [
  {
    chatId: -1,
    title: 'CuteGamingChat',
    positions: [
      { id: 1, title: 'Создатель', rank: 5, kind: 'post' },
      { id: 2, title: 'Администратор', rank: 4, kind: 'post' },
      { id: 3, title: 'Участник', rank: 0, kind: 'member' },
      { id: 4, title: 'Спам-блок', rank: 0, kind: 'spamblock' },
    ],
  },
]

describe('where an application can sit', () => {
  it('offers admin posts and skips the group creator, members and spam blocks', () => {
    const choices = adminSeatChoices(SAMPLE)
    expect(choices[0].posts.map((post) => post.title)).toEqual(['Администратор'])
  })

  it('includes spamblock when the group-admins desk asks for it', () => {
    const choices = adminSeatChoices(SAMPLE, { includeSpamblock: true })
    expect(choices[0].posts.map((post) => post.title)).toEqual(['Администратор', 'Спам-блок'])
  })

  it('labels kinds for the desk chips', () => {
    expect(positionKindLabel('spamblock')).toBe('Спам-блок')
    expect(positionKindLabel('post')).toBe('Админ')
  })

  it('reads a chat id typed into the search', () => {
    expect(typedChatId('-1001234567890')).toBe(-1001234567890)
    expect(typedChatId('альфа')).toBeNull()
  })
})
