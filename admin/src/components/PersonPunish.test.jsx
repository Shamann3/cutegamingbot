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
    expect(screen.queryByRole('button', { name: 'Банфулл' })).toBeNull()
    fireEvent.change(screen.getByPlaceholderText('что человек сделал'), { target: { value: 'снова флуд' } })
    fireEvent.click(screen.getByRole('button', { name: 'Выдать: Мут · 1 час' }))
    expect(onAct).toHaveBeenCalledWith({
      userId: '7',
      action: 'mute',
      untilSec: 3600,
      reason: 'снова флуд',
    })
  })

  it('can issue a project-wide ban when that right is open', async () => {
    vi.mocked(fetchPersonHistory).mockResolvedValue(history)
    const onAct = vi.fn().mockResolvedValue({})
    render(
      <PersonPunish
        chatId={-5}
        userId={7}
        actions={actions}
        wide={[{ id: 'banfull', label: 'Банфулл', hint: 'Бан на весь проект. Снять его из этой карточки нельзя.', needsUntil: true }]}
        onAct={onAct}
        onClose={() => {}}
      />,
    )
    fireEvent.click(await screen.findByRole('button', { name: 'Банфулл' }))
    expect(screen.getByText(/Бан на весь проект/)).toBeTruthy()
    fireEvent.change(screen.getByPlaceholderText('что человек сделал'), { target: { value: 'спам везде' } })
    fireEvent.click(screen.getByRole('button', { name: 'Выдать: Банфулл · 1 час' }))
    expect(onAct).toHaveBeenCalledWith({
      userId: '7',
      action: 'banfull',
      untilSec: 3600,
      reason: 'спам везде',
    })
  })

  it('explains a person who was not in the project yet and does not title the card with a raw id', async () => {
    vi.mocked(fetchPersonHistory).mockResolvedValue({
      ...history,
      name: '7',
      username: null,
      items: [],
      total: 0,
      notice: 'В Куте этого человека ещё не было. Записали его, чтобы наказание легло на карточку.',
    })
    render(<PersonPunish chatId={-5} userId={7} actions={actions} onAct={vi.fn()} onClose={() => {}} />)
    expect(await screen.findByRole('heading', { name: 'Человек' })).toBeTruthy()
    expect(screen.getByText(/ещё не было/)).toBeTruthy()
  })

  it('can hold a punishment down to the second and lifts a shorter span to 35', async () => {
    vi.mocked(fetchPersonHistory).mockResolvedValue(history)
    const onAct = vi.fn().mockResolvedValue({})
    render(
      <PersonPunish chatId={-5} userId={7} actions={actions} onAct={onAct} onClose={() => {}} />,
    )
    fireEvent.click(await screen.findByRole('button', { name: 'До секунды' }))
    fireEvent.change(screen.getByLabelText('Часы'), { target: { value: '0' } })
    fireEvent.change(screen.getByLabelText('Секунды'), { target: { value: '10' } })
    expect(screen.getByText(/уйдёт на 35/)).toBeTruthy()
    fireEvent.change(screen.getByPlaceholderText('что человек сделал'), { target: { value: 'флуд' } })
    fireEvent.click(screen.getByRole('button', { name: 'Выдать: Мут · 35 секунд' }))
    expect(onAct).toHaveBeenCalledWith({
      userId: '7',
      action: 'mute',
      untilSec: 35,
      reason: 'флуд',
    })
  })
})
