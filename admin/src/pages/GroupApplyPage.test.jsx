import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import GroupApplyPage from './GroupApplyPage'

vi.mock('../lib/adminClient', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchGroupRules: vi.fn(() => Promise.reject(Object.assign(new Error('API не отвечает'), { status: 500 }))),
}))

vi.mock('../components/AccentAura', () => ({ default: () => null }))
vi.mock('../components/EpsilonLogo', () => ({ default: () => null }))

afterEach(() => cleanup())

async function reachText() {
  render(<GroupApplyPage preview onBack={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: 'Открыть список' }))
  fireEvent.click(await screen.findByRole('button', { name: 'CuteGaming' }))
  await waitFor(() => expect(document.querySelector('.choice-sheet')).toBeNull())
  fireEvent.click(screen.getByRole('button', { name: 'Открыть список' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Модератор' }))
  await waitFor(() => expect(document.querySelector('.choice-sheet')).toBeNull())
}

describe('GroupApplyPage', () => {
  it('после короткого текста показывает, сколько ещё написать', async () => {
    await reachText()
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Слежу за чатом' } })
    expect(await screen.findByText('Ещё 6 символов — и откроются правила.')).toBeTruthy()
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Слежу за чатом по вечерам и разбираю споры спокойно.' } })
    expect(await screen.findByText('API не отвечает')).toBeTruthy()
  })
})
