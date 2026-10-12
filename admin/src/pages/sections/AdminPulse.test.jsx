import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AdminPulse from './AdminPulse'
import { fetchAdminPulse, fetchPersonHistory } from '../../lib/adminClient'

vi.mock('../../lib/adminClient', () => ({
  fetchAdminPulse: vi.fn(),
  fetchPersonHistory: vi.fn(),
}))

const REPORT = {
  available: true,
  period: 'month',
  from: '2026-10-01',
  to: '2026-10-12',
  total: 11,
    busiest: { userId: 2, name: 'Bob', username: 'bob', position: 'Модератор', messages: 9, share: 82, last: 'сегодня' },
  quietest: { userId: 3, name: 'Cia', position: 'Хелпер', messages: 0, share: 0, last: 'ещё не было' },
  people: [
    { userId: 2, name: 'Bob', username: 'bob', position: 'Модератор', messages: 9, share: 82, last: 'сегодня' },
    { userId: 1, name: 'Ann', position: 'Админ', messages: 2, share: 18, last: 'вчера' },
    { userId: 3, name: 'Cia', position: 'Хелпер', messages: 0, share: 0, last: 'ещё не было' },
  ],
}

describe('admin pulse', () => {
  afterEach(() => cleanup())

  it('names the busiest and the quietest admin', async () => {
    vi.mocked(fetchAdminPulse).mockResolvedValue(REPORT)
    vi.mocked(fetchPersonHistory).mockResolvedValue({
      available: true,
      counts: [{ action: 'mute', label: 'Мут', hint: 'этот чат', count: 1 }],
    })
    const open = vi.fn()
    render(<AdminPulse chatId={-5} onOpenUser={open} watch={[{ userId: 2, warns: 2 }]} />)
    expect(await screen.findByRole('button', { name: /Самый живой, Bob/ })).toBeTruthy()
    expect(screen.getByRole('button', { name: /Самый тихий, Cia/ })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /Самый живой, Bob/ }))
    expect(await screen.findByRole('dialog', { name: 'Bob' })).toBeTruthy()
    expect(screen.getByText('@bob · Модератор')).toBeTruthy()
    expect(screen.getByText('82% среди администраторов')).toBeTruthy()
    expect(screen.getByText(/Ещё одно предупреждение/)).toBeTruthy()
    expect(await screen.findByText('Мут')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Наказания этого человека' }))
    expect(open).toHaveBeenCalledWith(2)
    fireEvent.click(screen.getByRole('button', { name: /Cia, 0 сообщений/ }))
    expect(await screen.findByRole('dialog', { name: 'Cia' })).toBeTruthy()
    fireEvent.click(screen.getByRole('tab', { name: 'Год' }))
    await waitFor(() => {
      expect(fetchAdminPulse).toHaveBeenCalledWith(-5, { period: 'year', start: '', end: '' })
    })
  })
})
