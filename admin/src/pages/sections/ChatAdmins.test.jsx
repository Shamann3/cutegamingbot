import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ChatAdmins from './ChatAdmins'
import { actChatAdmin, fetchChatAdmins } from '../../lib/adminClient'

vi.mock('../../lib/adminClient', () => ({
  fetchChatAdmins: vi.fn(),
  actChatAdmin: vi.fn(),
}))

const BOARD = {
  admins: [
    {
      userId: 5,
      name: 'Аня',
      username: 'anya',
      status: 'administrator',
      title: '',
      isBot: false,
      isSelfBot: false,
      canDelete: true,
      canRestrict: true,
      canPromote: false,
    },
  ],
  history: [
    {
      id: 1,
      action: 'chat_admin_demote',
      detail: 'Снял админку: Иван · 9',
      actorName: 'Босс',
      at: '2026-10-11T18:27:00Z',
    },
  ],
  canAct: true,
  botCanPromote: true,
  selfId: 1,
  error: '',
}

describe('chat admins', () => {
  afterEach(() => cleanup())

  it('lists the group admins and asks before removing one', async () => {
    vi.mocked(fetchChatAdmins).mockResolvedValue(BOARD)
    vi.mocked(actChatAdmin).mockResolvedValue({ ...BOARD, note: 'Админка снята', history: BOARD.history })
    render(<ChatAdmins chatId={-100} />)
    expect(await screen.findByText('Аня')).toBeTruthy()
    expect(screen.getByText(/@anya/)).toBeTruthy()
    expect(screen.getByText('5')).toBeTruthy()
    expect(screen.getByText('Босс')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Снять' }))
    expect(screen.getByText(/Снять админку: Аня станет обычным участником/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить' }))
    await waitFor(() => {
      expect(actChatAdmin).toHaveBeenCalledWith(-100, 5, 'demote')
    })
    expect(await screen.findByText('Админка снята')).toBeTruthy()
  })
})
