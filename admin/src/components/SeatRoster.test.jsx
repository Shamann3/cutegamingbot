import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SeatRoster from './SeatRoster'

afterEach(() => cleanup())

const groups = [{
  chatId: -100,
  title: 'Cute',
  positions: [
    { id: 4, title: 'Хелпер', rank: 2, kind: 'post', prefix: 'хелпер' },
    { id: 5, title: 'Спам-блок', rank: 0, kind: 'spamblock', prefix: 'спам блок' },
  ],
  seats: [{
    userId: 7,
    chatId: -100,
    name: 'Иван',
    username: 'ivan',
    position: 'Хелпер',
    rank: 2,
    prefix: 'хелпер',
    mutedUntil: '2026-10-10T18:30:00',
    muteReason: 'флуд',
    banUntil: '',
    paused: false,
    warns: 2,
  }, {
    userId: 8,
    chatId: -100,
    name: 'Мария',
    position: 'Хелпер',
    rank: 2,
    banUntil: '2026-10-12T12:00:00',
    banReason: 'спам',
    paused: true,
    pauseUntil: '2026-10-12T12:00:00',
    mutedUntil: '',
  }, {
    userId: 9,
    chatId: -100,
    name: 'Пётр',
    position: 'Хелпер',
    rank: 2,
    paused: true,
    permanent: true,
    banUntil: '',
    mutedUntil: '',
  }],
}]

describe('SeatRoster', () => {
  it('shows every administrator and the punishment on the card', () => {
    render(<SeatRoster groups={groups} onLift={vi.fn()} onDismiss={vi.fn()} onReissue={vi.fn()} />)
    expect(screen.getByText(/Иван/)).toBeTruthy()
    expect(screen.getByText(/Мария/)).toBeTruthy()
    expect(screen.getByText(/Мут/)).toBeTruthy()
    expect(screen.getByText(/флуд/)).toBeTruthy()
    expect(screen.getByText(/Предупреждения/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Снять мут' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Снять бан' })).toBeTruthy()
    expect(screen.getByText(/Должность снята навсегда/)).toBeTruthy()
    expect(screen.getByText(/Вернуть может только создатель/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Вернуть должность' })).toBeNull()
  })

  it('lifts a mute and opens reissue under the card', () => {
    const onLift = vi.fn()
    const onReissue = vi.fn()
    render(<SeatRoster groups={groups} onLift={onLift} onDismiss={vi.fn()} onReissue={onReissue} />)
    fireEvent.click(screen.getByRole('button', { name: 'Снять мут' }))
    expect(onLift).toHaveBeenCalledWith(expect.objectContaining({ userId: 7 }), 'unmute')
    const card = screen.getByText(/Иван/).closest('article')
    fireEvent.click(withinCard(card, 'Перевыдать'))
    fireEvent.click(withinCard(card, 'Хелпер'))
    fireEvent.click(withinCard(card, 'Поставить должность'))
    expect(onReissue).toHaveBeenCalledWith(
      expect.objectContaining({ userId: 7 }),
      expect.objectContaining({ id: 4 }),
      expect.objectContaining({ termEnd: '' }),
    )
  })
})

function withinCard(card, name) {
  return Array.from(card.querySelectorAll('button')).find((button) => button.textContent === name)
}
