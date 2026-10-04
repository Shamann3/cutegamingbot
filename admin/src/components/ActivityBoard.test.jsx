import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ActivityBoard from './ActivityBoard'
import GroupArchive from './GroupArchive'
import { fetchGroupActivity } from '../lib/adminClient'

vi.mock('../lib/adminClient', () => ({
  fetchGroupActivity: vi.fn(),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const report = {
  available: true,
  messages: 40,
  writers: 2,
  periodMessages: 100,
  periodWriters: 4,
  previousMessages: 80,
  series: [{ date: '2026-10-01', messages: 40, writers: 2 }],
  people: [
    { userId: 7, name: 'Анна', username: 'anna', messages: 40 },
  ],
}

describe('ActivityBoard', () => {
  it('opens a person and can send them to the archive', async () => {
    vi.mocked(fetchGroupActivity).mockResolvedValue(report)
    const onOpenArchive = vi.fn()
    render(
      <ActivityBoard
        chatId={1}
        canArchive
        onOpenArchive={onOpenArchive}
        watch={[{ userId: 7, warns: 2 }]}
        repeats={new Map([[7, 3]])}
      />,
    )
    fireEvent.click(await screen.findByRole('button', { name: /Анна/ }))
    expect(screen.getByText('40%')).toBeTruthy()
    expect(screen.getByText(/Ещё одно предупреждение — бан в этом чате/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Наказания этого человека' }))
    expect(onOpenArchive).toHaveBeenCalledWith(7)
  })
})

describe('GroupArchive', () => {
  it('puts the lift on the card and asks for a reason there', () => {
    const onAct = vi.fn()
    render(
      <GroupArchive
        rows={[{ id: 1, action: 'ban', target_user_id: 7, targetName: 'Игрок', admin: 'Анна', reason: 'спам', at: '2026-10-01T12:00:00Z' }]}
        actions={[{ id: 'unban', label: 'Разбан' }, { id: 'ban', label: 'Бан', needsUntil: true }]}
        onAct={onAct}
      />,
    )
    expect(screen.getByRole('button', { name: 'Разбанить' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Разбанить' }))
    expect(screen.getByLabelText('Причина снятия')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Разбанить' })).toBeTruthy()
  })
})
