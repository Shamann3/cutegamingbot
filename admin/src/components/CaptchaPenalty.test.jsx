import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import CaptchaPenalty from './CaptchaPenalty'
import { fetchCaptchaPenalty, saveCaptchaPenalty } from '../lib/adminClient'

vi.mock('../lib/adminClient', () => ({
  fetchCaptchaPenalty: vi.fn(),
  saveCaptchaPenalty: vi.fn(),
}))

vi.mock('../lib/notify', () => ({ notifyAdmin: vi.fn() }))

const pack = {
  enabled: false,
  strikes: 5,
  action: 'mute',
  seconds: 3600,
  sentence: 'Наказание выключено. Ошибки капчи только меняют карточку.',
  cards: [
    { id: 'mute', label: 'Мут', place: 'Этот чат', hint: 'Не может писать.', needsUntil: true },
    { id: 'kick', label: 'Кик', place: 'Этот чат', hint: 'Убрать из группы.', needsUntil: false },
    { id: 'banfull', label: 'Банфулл', place: 'Весь проект', hint: 'Бан везде.', needsUntil: true },
  ],
}

afterEach(() => cleanup())

describe('CaptchaPenalty', () => {
  it('saves a streak of five and banfull for every group', async () => {
    vi.mocked(fetchCaptchaPenalty).mockResolvedValue(pack)
    vi.mocked(saveCaptchaPenalty).mockResolvedValue({ ...pack, enabled: true, action: 'banfull' })
    render(<CaptchaPenalty />)
    expect(await screen.findByText('Наказание за капчу')).toBeTruthy()
    fireEvent.click(screen.getByRole('switch', { name: /Наказывать за серию ошибок/ }))
    fireEvent.click(screen.getByRole('button', { name: /Банфулл/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Записать наказание' }))
    await waitFor(() => expect(saveCaptchaPenalty).toHaveBeenCalledWith({
      enabled: true,
      strikes: 5,
      action: 'banfull',
      seconds: 3600,
    }))
  })
})
