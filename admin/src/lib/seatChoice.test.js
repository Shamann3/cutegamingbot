import { describe, expect, it } from 'vitest'
import { adminSeatChoices, typedChatId } from './seatChoice'

describe('where an application can sit', () => {
  it('offers admin posts and skips the group creator, members and spam blocks', () => {
    const choices = adminSeatChoices([
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
    ])
    expect(choices[0].posts.map((post) => post.title)).toEqual(['Администратор'])
  })

  it('reads a chat id typed into the search', () => {
    expect(typedChatId('-1001234567890')).toBe(-1001234567890)
    expect(typedChatId('альфа')).toBeNull()
  })
})
