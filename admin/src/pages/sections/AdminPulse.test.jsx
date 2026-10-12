import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AdminPulse from './AdminPulse'
import { fetchAdminPulse } from '../../lib/adminClient'

vi.mock('../../lib/adminClient', () => ({
  fetchAdminPulse: vi.fn(),
}))

const REPORT = {
  available: true,
  period: 'month',
  from: '2026-10-01',
  to: '2026-10-12',
  total: 11,
  busiest: { userId: 2, name: 'Bob', position: 'Модератор', messages: 9, share: 82, last: 'сегодня' },
  quietest: { userId: 3, name: 'Cia', position: 'Хелпер', messages: 0, share: 0, last: 'ещё не было' },
  people: [
    { userId: 2, name: 'Bob', position: 'Модератор', messages: 9, share: 82, last: 'сегодня' },
    { userId: 1, name: 'Ann', position: 'Админ', messages: 2, share: 18, last: 'вчера' },
    { userId: 3, name: 'Cia', position: 'Хелпер', messages: 0, share: 0, last: 'ещё не было' },
  ],
}

describe('admin pulse', () => {
  afterEach(() => cleanup())

  it('names the busiest and the quietest admin', async () => {
    vi.mocked(fetchAdminPulse).mockResolvedValue(REPORT)
    const open = vi.fn()
    render(<AdminPulse chatId={-5} onOpenUser={open} />)
    expect((await screen.findAllByText('Bob')).length).toBeGreaterThan(1)
    expect(screen.getByText('Самый живой')).toBeTruthy()
    expect(screen.getByText('Самый тихий')).toBeTruthy()
    expect(screen.getAllByText('Cia').length).toBeGreaterThan(0)
    fireEvent.click(screen.getAllByRole('button', { name: 'Bob' })[0])
    expect(open).toHaveBeenCalledWith(2)
    fireEvent.click(screen.getByRole('tab', { name: 'Год' }))
    await waitFor(() => {
      expect(fetchAdminPulse).toHaveBeenCalledWith(-5, { period: 'year', start: '', end: '' })
    })
  })
})
