import { describe, expect, it } from 'vitest'
import { placeBlock, supplyNotice } from './positionSupply'

describe('position supply', () => {
  it('keeps the group creator and a second spam block out', () => {
    expect(placeBlock({ title: 'Создатель группы', kind: 'post', rank: 5, targetTitles: [], targetKinds: [] }))
      .toMatch(/не копируется/)
    expect(placeBlock({ title: 'Спам блок', kind: 'spamblock', rank: 0, targetTitles: [], targetKinds: ['spamblock'] }))
      .toMatch(/уже есть/)
    expect(placeBlock({ title: 'Администратор ГЧ', kind: 'post', rank: 4, targetTitles: ['Модератор'], targetKinds: ['post'] }))
      .toBe('')
  })

  it('names what was placed and what was skipped', () => {
    expect(supplyNotice({
      placed: [{ title: 'Администратор ГЧ' }],
      skipped: [{ title: 'Спам блок', reason: 'Спам-блок в этой группе уже есть' }],
    }, 'Поставлена должность')).toBe(
      'Поставлена должность «Администратор ГЧ». Спам блок: Спам-блок в этой группе уже есть',
    )
  })
})
