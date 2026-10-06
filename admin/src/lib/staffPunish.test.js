import { describe, expect, it } from 'vitest'
import { isLift, punishProblem, punishReceipt, punishShelves, punishVerb } from './staffPunish'

describe('staffPunish', () => {
  it('keeps only the scopes this role was given', () => {
    const shelves = punishShelves([
      { id: 'mute', scope: 'chat', label: 'Мут' },
      { id: 'banfull', scope: 'full', label: 'Банфулл' },
    ])
    expect(shelves.map((shelf) => shelf.id)).toEqual(['chat', 'full'])
    expect(shelves[0].items.map((item) => item.id)).toEqual(['mute'])
  })

  it('refuses a missing reason, a zero span and punishing yourself', () => {
    const action = { id: 'mute', needsUntil: true, label: 'Мут' }
    expect(punishProblem({ action, chatId: '-1', spanSec: 3600, reason: ' ', actorId: 1, targetId: 2 }))
      .toMatch(/причин/i)
    expect(punishProblem({ action, chatId: '-1', spanSec: 0, reason: 'спам', actorId: 1, targetId: 2 }))
      .toMatch(/срок/i)
    expect(punishProblem({ action, chatId: '-1', spanSec: 3600, reason: 'спам', actorId: 5, targetId: 5 }))
      .toBe('Себя наказать нельзя')
    expect(punishProblem({
      action: { id: 'unban', needsUntil: false, label: 'Снять бан' },
      chatId: '-1',
      spanSec: 0,
      reason: 'ошибка',
      actorId: 5,
      targetId: 5,
    })).toBe('Снять наказание с самого себя нельзя')
  })

  it('names the place in the receipt and treats lifts as lifts', () => {
    expect(isLift('unmuteall')).toBe(true)
    expect(isLift('ban')).toBe(false)
    expect(punishVerb({ id: 'kick', label: 'Кик', needsUntil: false }, 0)).toBe('Выдать: Кик')
    expect(punishReceipt({ label: 'Бан', scope: 'chat', chatTitle: 'Чатик', untilSec: 3600 }))
      .toContain('Чатик')
  })
})
