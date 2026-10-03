import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import GroupApplyPage from './GroupApplyPage'

vi.mock('../lib/adminClient', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchGroupOpen: vi.fn(() => Promise.reject(new Error('API не отвечает'))),
  fetchGroupRules: vi.fn(() => Promise.reject(new Error('API не отвечает'))),
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
    const rulesLink = await screen.findByRole('link', { name: 'Канал с правилами' })
    expect(screen.getByText('Прочтите правила')).toBeTruthy()
    expect(rulesLink.getAttribute('href')).toBe('https://t.me/CuteRules')
    expect(screen.getByText('При открытии правил нужно будет перезайти в панель и написать заявку заново.')).toBeTruthy()
    expect(screen.getByText('Вы ознакомлены с правилами проекта?')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Отправить заявку' })).toBeNull()
    fireEvent.click(screen.getByRole('checkbox', { name: 'Я знаю правила' }))
    expect(screen.getByRole('button', { name: 'Отправить заявку' })).toBeTruthy()
  })

  it('без ответа сервера показывает правила и не пишет про API', async () => {
    render(<GroupApplyPage onBack={() => {}} />)
    expect(await screen.findByRole('link', { name: 'Канал с правилами' })).toBeTruthy()
    expect(screen.getByText('Прочтите правила')).toBeTruthy()
    expect(screen.getByText('Вы ознакомлены с правилами проекта?')).toBeTruthy()
    expect(screen.getByText('При открытии правил нужно будет перезайти в панель и написать заявку заново.')).toBeTruthy()
    expect(screen.queryByText('API не отвечает')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Повторить' })).toBeNull()
  })
})
