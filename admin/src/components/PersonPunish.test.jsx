import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PersonPunish from './PersonPunish'
import { fetchPersonHistory } from '../lib/adminClient'

vi.mock('../lib/adminClient', () => ({
  fetchPersonHistory: vi.fn(),
}))

vi.mock('../lib/memeSounds', () => ({
  playMeme: vi.fn(),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const history = {
  available: true,
  userId: 7,
  name: 'Анна',
  username: 'anna',
  total: 2,
  clipped: false,
  items: [
    { id: 2, at: '2026-10-04T12:00:00Z', action: 'banfull', scope: 'full', chatId: -100, admin: 'Марк', reason: 'спам везде', minutes: 0 },
    { id: 1, at: '2026-09-01T12:00:00Z', action: 'mute', scope: 'chat', chatId: -5, admin: 'Лера', reason: 'флуд', minutes: 60 },
  ],
}

const actions = [
  { id: 'mute', label: 'Мут', needsUntil: true },
  { id: 'ban', label: 'Бан', needsUntil: true },
  { id: 'unmute', label: 'Снять мут' },
  { id: 'unban', label: 'Снять бан' },
]

describe('PersonPunish', () => {
  it('shows earlier punishments and only the punishments this seat can issue', async () => {
    vi.mocked(fetchPersonHistory).mockResolvedValue(history)
    const onAct = vi.fn().mockResolvedValue({})
    render(
      <PersonPunish chatId={-5} userId={7} actions={actions} onAct={onAct} onClose={() => {}} />,
    )
    expect(await screen.findByRole('heading', { name: 'Анна' })).toBeTruthy()
    expect(screen.getByText('спам везде')).toBeTruthy()
    expect(screen.getByText('флуд')).toBeTruthy()
    expect(screen.getByText(/Весь проект/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Размутить' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Разбанить' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Мут' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Снять мут' })).toBeNull()
    fireEvent.change(screen.getByPlaceholderText('что человек сделал'), { target: { value: 'снова флуд' } })
    fireEvent.click(screen.getByRole('button', { name: 'Выдать: Мут' }))
    expect(onAct).toHaveBeenCalledWith({
      userId: '7',
      action: 'mute',
      hours: '1',
      reason: 'снова флуд',
    })
  })
})
