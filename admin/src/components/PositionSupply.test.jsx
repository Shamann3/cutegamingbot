import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PositionSupply from './PositionSupply'
import { copyGroupPositions, fetchPositionTemplates, fetchRightsBoard, placePositionTemplate } from '../lib/adminClient'

vi.mock('../lib/adminClient', () => ({
  fetchRightsBoard: vi.fn(),
  fetchPositionTemplates: vi.fn(),
  placePositionTemplate: vi.fn(),
  copyGroupPositions: vi.fn(),
  pushGroupPositions: vi.fn(),
}))

const board = {
  groups: [
    {
      chatId: -5,
      title: 'CuteGamingChat',
      positions: [
        { id: 1, title: 'Создатель группы', rank: 5, kind: 'post' },
        { id: 2, title: 'Модератор', rank: 2, kind: 'post' },
        { id: 3, title: 'Спам блок', rank: 0, kind: 'spamblock' },
      ],
    },
    {
      chatId: -9,
      title: 'Новая группа',
      positions: [
        { id: 8, title: 'Создатель группы', rank: 5, kind: 'post' },
        { id: 9, title: 'Спам блок', rank: 0, kind: 'spamblock' },
      ],
    },
  ],
}

afterEach(() => cleanup())

describe('PositionSupply', () => {
  it('places a voice-chat template into the open group', async () => {
    vi.mocked(fetchRightsBoard).mockResolvedValue(board)
    vi.mocked(fetchPositionTemplates).mockResolvedValue({
      templates: [{
        id: 'voice',
        title: 'Администратор ГЧ',
        kind: 'post',
        rank: 4,
        blurb: 'Пишет как обычный участник. Единственное право администратора — голосовой чат.',
      }],
    })
    vi.mocked(placePositionTemplate).mockResolvedValue({ placed: [{ title: 'Администратор ГЧ' }], skipped: [] })
    const onPlaced = vi.fn()
    render(<PositionSupply chatId={-9} onPlaced={onPlaced} />)
    fireEvent.click(screen.getByRole('button', { name: 'Заготовки' }))
    expect(await screen.findByText(/голосовой чат/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Поставить Администратор ГЧ' }))
    await waitFor(() => expect(placePositionTemplate).toHaveBeenCalledWith({ chat_id: -9, template_id: 'voice' }))
    await waitFor(() => expect(onPlaced).toHaveBeenCalledWith('Поставлена должность «Администратор ГЧ»'))
  })

  it('copies a post and leaves the creator and the existing spam block', async () => {
    vi.mocked(fetchRightsBoard).mockResolvedValue(board)
    vi.mocked(copyGroupPositions).mockResolvedValue({ placed: [{ title: 'Модератор' }], skipped: [] })
    const onPlaced = vi.fn()
    render(<PositionSupply chatId={-9} onPlaced={onPlaced} />)
    fireEvent.click(screen.getByRole('button', { name: 'Из другой группы' }))
    expect(await screen.findByText('CuteGamingChat')).toBeTruthy()
    expect(screen.getAllByText(/не копируется/).length).toBeGreaterThan(0)
    expect(screen.getByText('Должность с таким названием уже есть')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /Модератор/ }))
    fireEvent.click(screen.getByRole('button', { name: /Перенести выбранные/ }))
    await waitFor(() => expect(copyGroupPositions).toHaveBeenCalledWith({
      chat_id: -9,
      source_chat_id: -5,
      ids: [2],
    }))
    await waitFor(() => expect(onPlaced).toHaveBeenCalled())
  })

  it('opens the push window from this group and loads the board once', async () => {
    vi.mocked(fetchRightsBoard).mockClear()
    vi.mocked(fetchRightsBoard).mockResolvedValue(board)
    render(<PositionSupply chatId={-5} onPlaced={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'В другие группы' }))
    expect(await screen.findByRole('dialog', { name: 'В другие группы' })).toBeTruthy()
    expect(await screen.findByRole('button', { name: 'Модератор, ранг 2' })).toBeTruthy()
    expect(screen.getByText('Новая группа', { selector: '.push-zone-name strong' })).toBeTruthy()
    expect(fetchRightsBoard).toHaveBeenCalledTimes(1)
  })
})
