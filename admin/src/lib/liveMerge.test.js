import { describe, expect, it } from 'vitest'
import {
  arrivalLine,
  hiddenLine,
  moderationDelta,
  pileLine,
  placeLogs,
  samePulse,
} from './liveMerge'

describe('live archive merge', () => {
  it('does not treat the first page as a sudden arrival', () => {
    const delta = moderationDelta(undefined, [{ id: 4, action: 'ban' }])
    expect(delta.fresh).toEqual([])
    expect(delta.recent).toEqual([{ id: 4, action: 'ban' }])
  })

  it('keeps a new punishment at the top and notices a verdict change', () => {
    const delta = moderationDelta(
      [{ id: 2, action: 'mute', sortVerdict: null, reason: 'спам' }],
      [
        { id: 9, action: 'ban', sortVerdict: null, reason: 'оскорбление' },
        { id: 2, action: 'mute', sortVerdict: 'clear', reason: 'спам' },
      ],
    )
    expect(delta.fresh.map((row) => row.id)).toEqual([9])
    expect(delta.changed).toBe(true)
    expect(delta.recent[0].id).toBe(9)
  })

  it('places a dated row above the page and a typed row inside its group', () => {
    const dated = placeLogs(
      [{ id: 3, actionType: 'mute' }, { id: 1, actionType: 'ban' }],
      [{ id: 8, actionType: 'ban' }],
      'date',
    )
    expect(dated.items.map((row) => row.id)).toEqual([8, 3, 1])

    const typed = placeLogs(
      [
        { id: 4, actionType: 'ban' },
        { id: 2, actionType: 'mute' },
      ],
      [{ id: 9, actionType: 'mute' }],
      'type',
    )
    expect(typed.items.map((row) => row.id)).toEqual([4, 9, 2])
    expect(placeLogs(dated.items, [{ id: 8, actionType: 'ban' }], 'date').fresh).toEqual([])
  })

  it('names the punishment that landed and the one the filter hides', () => {
    expect(arrivalLine([{ action: 'warn' }])).toBe('Новое предупреждение уже в этом списке.')
    expect(arrivalLine([{ action: 'ban' }, { action: 'mute' }])).toBe('В этот список добавлено 2.')
    expect(hiddenLine({ action: 'kick' })).toBe('Новый кик уже в архиве. Этот фильтр его не показывает.')
    expect(pileLine(1)).toBe('Пока эта карточка открыта, новое наказание уже в колоде.')
    expect(pileLine(3)).toBe('Пока эта карточка открыта, в колоду пришло ещё 3.')
  })

  it('ignores an unchanged count snapshot', () => {
    const moderation = {
      actions30d: 4, mutes: 1, bans: 1, warns: 2, kicks: 0,
      watch: [{ userId: 7, warns: 2 }],
    }
    expect(samePulse(moderation, { ...moderation })).toBe(true)
    expect(samePulse(moderation, { ...moderation, bans: 2 })).toBe(false)
    const removed = { people: 3, month: 1, active: 2 }
    expect(samePulse(moderation, { ...moderation, captchaRemoved: removed })).toBe(false)
    expect(samePulse({ ...moderation, captchaRemoved: removed }, { ...moderation, captchaRemoved: removed })).toBe(true)
  })
})
