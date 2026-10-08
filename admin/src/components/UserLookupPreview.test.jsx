import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import UserLookupPreview from './UserLookupPreview'
import { glanceAdminUser, searchAdminUsers } from '../lib/adminClient'

vi.mock('../lib/adminClient', () => ({
  searchAdminUsers: vi.fn(),
  glanceAdminUser: vi.fn(),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('UserLookupPreview', () => {
  it('shows a telegram person who is not in the project yet', async () => {
    vi.mocked(searchAdminUsers).mockResolvedValue({ results: [] })
    vi.mocked(glanceAdminUser).mockResolvedValue({
      status: 'outside',
      message: 'В Куте этого человека ещё нет. Наказание добавит его в базу.',
      user: { userId: 8827084733, displayName: 'Prayz', username: 'Prayz00', outside: true, balance: null },
    })
    const onResolved = vi.fn()
    render(
      <UserLookupPreview
        value="Prayz00"
        allowOutside
        chatId={-100}
        onChange={() => {}}
        onResolved={onResolved}
      />,
    )
    expect(await screen.findByText('Prayz')).toBeTruthy()
    expect(screen.getByText(/ещё не в Куте/)).toBeTruthy()
    expect(screen.getByRole('status').textContent).toMatch(/добавит его в базу/)
    expect(onResolved).toHaveBeenCalledWith(expect.objectContaining({ userId: 8827084733 }))
    expect(glanceAdminUser).toHaveBeenCalledWith('Prayz00', -100)
  })

  it('keeps a player already in the project on the database card', async () => {
    vi.mocked(searchAdminUsers).mockResolvedValue({
      results: [{ userId: 7, displayName: 'Анна', username: 'anna', balance: 10 }],
    })
    render(<UserLookupPreview value="anna" allowOutside onChange={() => {}} onResolved={() => {}} />)
    expect(await screen.findByText('Анна')).toBeTruthy()
    expect(glanceAdminUser).not.toHaveBeenCalled()
  })
})
