import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchGroupOpen, submitGroupApplication } from '../lib/adminClient'
import GroupApplyPage from './GroupApplyPage'

const OPEN_GROUPS = {
  positions: [
    {
      chatId: -1001,
      title: 'CuteGaming',
      positionId: 1,
      position: 'Модератор',
      rights: ['view_members'],
    },
  ],
  mine: [],
}

async function fillApplication() {
  fireEvent.click(screen.getByRole('checkbox', { name: 'Я знаю правила' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Открыть список' }))
  fireEvent.click(await screen.findByRole('button', { name: 'CuteGaming' }))
  await waitFor(() => expect(document.querySelector('.choice-sheet')).toBeNull())
  fireEvent.click(screen.getByRole('button', { name: 'Открыть список' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Модератор' }))
  await waitFor(() => expect(document.querySelector('.choice-sheet')).toBeNull())
  fireEvent.change(screen.getByRole('textbox'), {
    target: { value: 'Слежу за чатом по вечерам и разбираю споры спокойно.' },
  })
  return screen.findByRole('button', { name: 'Отправить заявку' })
}

vi.mock('../lib/adminClient', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchGroupOpen: vi.fn(() => Promise.reject(new Error('API не отвечает'))),
  fetchGroupRules: vi.fn(() => Promise.reject(new Error('API не отвечает'))),
  submitGroupApplication: vi.fn(() => Promise.resolve({ ok: true, id: 42 })),
}))

vi.mock('../components/AccentAura', () => ({ default: () => null }))
vi.mock('../components/EpsilonLogo', () => ({ default: () => null }))

afterEach(() => {
  cleanup()
  fetchGroupOpen.mockReset()
  fetchGroupOpen.mockRejectedValue(new Error('API не отвечает'))
  submitGroupApplication.mockReset()
})

describe('GroupApplyPage', () => {
  it('идёт строго по шагам и кнопку отправки открывает последней', async () => {
    render(<GroupApplyPage preview onBack={() => {}} />)
    expect(screen.getByRole('link', { name: 'Канал с правилами' }).getAttribute('href')).toBe('https://t.me/CuteRules')
    expect(screen.queryByRole('button', { name: 'Открыть список' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Отправить заявку' })).toBeNull()

    fireEvent.click(screen.getByRole('checkbox', { name: 'Я знаю правила' }))
    expect(screen.queryByRole('button', { name: 'Отправить заявку' })).toBeNull()
    expect(screen.queryByRole('textbox')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Открыть список' }))
    fireEvent.click(await screen.findByRole('button', { name: 'CuteGaming' }))
    await waitFor(() => expect(document.querySelector('.choice-sheet')).toBeNull())
    expect(screen.queryByRole('button', { name: 'Отправить заявку' })).toBeNull()
    expect(screen.queryByRole('textbox')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Открыть список' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Модератор' }))
    await waitFor(() => expect(document.querySelector('.choice-sheet')).toBeNull())
    expect(screen.queryByRole('button', { name: 'Отправить заявку' })).toBeNull()

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Слежу за чатом' } })
    expect(await screen.findByText('Ещё 6 символов')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Отправить заявку' })).toBeNull()

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Слежу за чатом по вечерам и разбираю споры спокойно.' } })
    expect(await screen.findByRole('button', { name: 'Отправить заявку' })).toBeTruthy()
  })

  it('без ответа сервера показывает правила и не пишет про API', async () => {
    render(<GroupApplyPage onBack={() => {}} />)
    expect(await screen.findByRole('link', { name: 'Канал с правилами' })).toBeTruthy()
    expect(screen.getByText('Прочтите правила')).toBeTruthy()
    expect(screen.getByText('Вы ознакомлены с правилами проекта?')).toBeTruthy()
    expect(screen.getByText('При открытии правил нужно будет перезайти в панель и написать заявку заново.')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Отправить заявку' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Открыть список' })).toBeNull()
    expect(screen.queryByText('API не отвечает')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Повторить' })).toBeNull()

    fireEvent.click(screen.getByRole('checkbox', { name: 'Я знаю правила' }))
    expect(await screen.findByText('Группы не открылись.')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Открыть ещё раз' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Отправить заявку' })).toBeNull()
  })

  it('после отправки оставляет заявку на экране', async () => {
    fetchGroupOpen.mockResolvedValue(OPEN_GROUPS)
    submitGroupApplication.mockResolvedValue({ ok: true, id: 42 })
    render(<GroupApplyPage onBack={() => {}} />)
    fireEvent.click(await fillApplication())
    expect(await screen.findByText('Заявка отправлена')).toBeTruthy()
    expect(screen.getAllByText(/CuteGaming/).length).toBeGreaterThan(0)
    expect(screen.getByText('На рассмотрении')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Отправить заявку' })).toBeNull()
    expect(submitGroupApplication).toHaveBeenCalledTimes(1)
    expect(submitGroupApplication).toHaveBeenCalledWith({
      chat_id: -1001,
      position_id: 1,
      body: 'Слежу за чатом по вечерам и разбираю споры спокойно.',
      rules_read: true,
    })
  })

  it('если заявка не ушла, пишет это у кнопки', async () => {
    fetchGroupOpen.mockResolvedValue(OPEN_GROUPS)
    submitGroupApplication.mockRejectedValue(new Error('API не отвечает'))
    render(<GroupApplyPage onBack={() => {}} />)
    fireEvent.click(await fillApplication())
    expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'Заявка не ушла. Нажмите ещё раз.')
    expect(screen.getByRole('button', { name: 'Отправить заявку' })).toBeTruthy()
    expect(screen.queryByText('API не отвечает')).toBeNull()
  })
})
