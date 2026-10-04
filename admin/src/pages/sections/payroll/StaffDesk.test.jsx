import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import StaffDesk from './StaffDesk'
import { fetchStaffWork, sortStaffDeed, unsortStaffDeed } from '../../../lib/adminClient'

vi.mock('../../../lib/adminClient', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchStaffWork: vi.fn(),
  sortStaffDeed: vi.fn(),
  unsortStaffDeed: vi.fn(),
  isPanelPreviewMode: vi.fn(() => false),
}))

vi.mock('../../../components/PhotoLook', () => ({
  default: () => <div>фото</div>,
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const card = {
  id: 7,
  actionLabel: 'Бан',
  targetName: 'Игрок',
  adminName: 'Пётр',
  createdAt: '2026-10-01T12:00:00Z',
  durationMinutes: 60,
  reason: 'Спам в чате',
  hasProof: false,
  band: 'reason',
  chatTitle: 'Кьют',
  scopeLabel: 'одна группа',
  chain: [{ role: 'admin', id: 4, name: 'Анна', verdict: 'wrong', label: 'Наказание выдано неправильно' }],
}

describe('StaffDesk', () => {
  it('says the desk is empty until an administrator has answered', async () => {
    vi.mocked(fetchStaffWork).mockResolvedValue({ waiting: 0, card: null })
    render(<StaffDesk />)
    expect(await screen.findByText(/Сейчас проверять нечего/)).toBeTruthy()
  })

  it('shows the previous administrator and offers an unban request', async () => {
    vi.mocked(fetchStaffWork).mockResolvedValue({ waiting: 1, card })
    render(<StaffDesk />)
    expect(await screen.findByText('Анна: наказание выдано неправильно')).toBeTruthy()
    expect(screen.getByText(/указал, что оно выдано неправильно/)).toBeTruthy()
    expect(screen.getByRole('button', { name: /Подать заявку на разблокировку/ }).className).toContain('is-ask')
    expect(screen.queryByRole('button', { name: /В зарплату/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Мимо/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Выплатить/ })).toBeNull()
  })

  it('sends a clear answer without asking to lift', async () => {
    vi.mocked(fetchStaffWork)
      .mockResolvedValueOnce({ waiting: 1, card })
      .mockResolvedValue({ waiting: 0, card: null })
    vi.mocked(sortStaffDeed).mockResolvedValue({ ok: true, next: 'creator' })
    render(<StaffDesk />)
    expect(await screen.findByText('Бан · Игрок')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /^Подходит/ }))
    expect(await screen.findByText(/Сейчас проверять нечего/)).toBeTruthy()
    expect(sortStaffDeed).toHaveBeenCalledWith(7, 'clear', false)
  })

  it('files an unban request as its own action', async () => {
    vi.mocked(fetchStaffWork)
      .mockResolvedValueOnce({ waiting: 1, card })
      .mockResolvedValue({ waiting: 0, card: null })
    vi.mocked(sortStaffDeed).mockResolvedValue({ ok: true, next: 'creator' })
    render(<StaffDesk />)
    expect(await screen.findByText('Бан · Игрок')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /Подать заявку на разблокировку/ }))
    expect(await screen.findByText(/Заявка на разблокировку ушла создателю/)).toBeTruthy()
    expect(sortStaffDeed).toHaveBeenCalledWith(7, 'wrong', true)
  })

  it('takes the last staff answer back', async () => {
    vi.mocked(fetchStaffWork)
      .mockResolvedValueOnce({ waiting: 1, card })
      .mockResolvedValueOnce({ waiting: 0, card: null })
      .mockResolvedValue({ waiting: 1, card })
    vi.mocked(sortStaffDeed).mockResolvedValue({ ok: true, next: 'creator' })
    vi.mocked(unsortStaffDeed).mockResolvedValue({ ok: true })
    render(<StaffDesk />)
    expect(await screen.findByText('Бан · Игрок')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /^Подходит/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'Вернуть' }))
    expect(await screen.findByText('Ответ отменён. Карточка снова перед вами.')).toBeTruthy()
    expect(unsortStaffDeed).toHaveBeenCalledWith(7)
  })
})
