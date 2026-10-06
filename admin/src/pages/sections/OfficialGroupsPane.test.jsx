import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import OfficialGroupsPane from './OfficialGroupsPane'
import { fetchRightsBoard, markGroupOfficial, searchGroupsStudio } from '../../lib/adminClient'

vi.mock('../../lib/adminClient', () => ({
  fetchRightsBoard: vi.fn(),
  markGroupOfficial: vi.fn(),
  searchGroupsStudio: vi.fn(),
}))

afterEach(() => cleanup())

describe('OfficialGroupsPane', () => {
  it('lists official groups and can mark a found chat', async () => {
    vi.mocked(fetchRightsBoard).mockResolvedValue({
      groups: [{ chatId: -5, title: 'CuteGamingChat', username: 'cute', positions: [{ id: 2, title: 'Администратор', rank: 4, kind: 'post' }], seats: [] }],
    })
    vi.mocked(searchGroupsStudio).mockResolvedValue({
      items: [{ chat_id: -9, name: 'Новая', username: 'newchat' }],
    })
    vi.mocked(markGroupOfficial).mockResolvedValue({ ok: true })
    render(<OfficialGroupsPane />)
    expect(await screen.findByText('CuteGamingChat')).toBeTruthy()
    expect(screen.getAllByText(/кто админ/i).length).toBeGreaterThan(0)
    fireEvent.change(screen.getByPlaceholderText('Название, @username или id'), { target: { value: 'Новая' } })
    fireEvent.click(screen.getByRole('button', { name: 'Найти' }))
    expect(await screen.findByText('Новая')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Сделать официальной' }))
    expect(markGroupOfficial).toHaveBeenCalledWith(expect.objectContaining({ chat_id: -9, official: true }))
  })
})
