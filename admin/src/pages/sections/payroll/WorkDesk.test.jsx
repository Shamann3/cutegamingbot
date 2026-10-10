import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import WorkDesk from './WorkDesk'
import { fetchDeedWork, isPanelPreviewMode, sortDeed, unsortDeed } from '../../../lib/adminClient'

vi.mock('../../../lib/adminClient', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchDeedWork: vi.fn(),
  sortDeed: vi.fn(),
  unsortDeed: vi.fn(),
  isPanelPreviewMode: vi.fn(() => false),
}))

vi.mock('../../../components/PhotoLook', () => ({
  default: () => <div>фото</div>,
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const EMPTY = 'Сейчас проверять нечего. Новые наказания коллег появятся здесь.'

const card = {
  id: 7,
  actionLabel: 'Бан',
  targetName: 'Игрок',
  adminName: 'Анна',
  createdAt: '2026-10-01T12:00:00Z',
  durationMinutes: 60,
  reason: 'Спам в чате',
  hasProof: false,
  band: 'reason',
  chatTitle: 'Кьют',
  scopeLabel: 'одна группа',
  unclearCount: 0,
}

describe('WorkDesk', () => {
  it('says there is nothing to check', async () => {
    vi.mocked(fetchDeedWork).mockResolvedValue({ waiting: 0, card: null })
    render(<WorkDesk />)
    expect(await screen.findByText(EMPTY)).toBeTruthy()
  })

  it('names the answers and colours them', async () => {
    vi.mocked(fetchDeedWork).mockResolvedValue({ waiting: 3, card })
    render(<WorkDesk />)
    expect(await screen.findByText('Бан · Игрок')).toBeTruthy()
    expect(screen.getByText('Причина наказания')).toBeTruthy()
    expect(screen.getByText('Спам в чате')).toBeTruthy()
    expect(screen.getByText(/Записал: Анна/)).toBeTruthy()
    expect(screen.getByText('наказания ждут вашей проверки')).toBeTruthy()
    expect(screen.getByText('Фото нет, есть причина')).toBeTruthy()
    expect(screen.getByRole('button', { name: /^Подходит/ }).className).toContain('is-clear')
    expect(screen.getByRole('button', { name: /^Наказание выдано неправильно/ }).className).toContain('is-wrong')
    expect(screen.getByRole('button', { name: /^Непонятно/ }).className).toContain('is-weak')
    expect(screen.queryByRole('button', { name: /В зарплату/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Мимо/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Сами/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Выплатить/ })).toBeNull()
  })

  it('sends a fitting answer and keeps the next card moving', async () => {
    vi.mocked(fetchDeedWork)
      .mockResolvedValueOnce({ waiting: 1, card })
      .mockResolvedValueOnce({ waiting: 0, card: null })
    vi.mocked(sortDeed).mockResolvedValue({ ok: true, next: 'staff' })
    vi.mocked(isPanelPreviewMode).mockReturnValue(false)
    render(<WorkDesk />)
    expect(await screen.findByText('Бан · Игрок')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /^Подходит/ }))
    expect(await screen.findByText(EMPTY)).toBeTruthy()
    expect(screen.getByText(/^Подходит\. Сотрудник проекта/)).toBeTruthy()
    expect(sortDeed).toHaveBeenCalledWith(7, 'clear')
  })

  it('takes the last answer back', async () => {
    vi.mocked(fetchDeedWork)
      .mockResolvedValueOnce({ waiting: 1, card })
      .mockResolvedValueOnce({ waiting: 0, card: null })
      .mockResolvedValue({ waiting: 1, card })
    vi.mocked(sortDeed).mockResolvedValue({ ok: true })
    vi.mocked(unsortDeed).mockResolvedValue({ ok: true })
    render(<WorkDesk />)
    expect(await screen.findByText('Бан · Игрок')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /^Наказание выдано неправильно/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'Вернуть' }))
    expect(sortDeed).toHaveBeenCalledWith(7, 'wrong')
    expect(await screen.findByText('Ответ отменён. Карточка снова перед вами.')).toBeTruthy()
    expect(unsortDeed).toHaveBeenCalledWith(7)
    expect(await screen.findByText('Бан · Игрок')).toBeTruthy()
  })

  it('passes an unclear card to the next stage and hides it from other admins', async () => {
    vi.mocked(fetchDeedWork)
      .mockResolvedValueOnce({ waiting: 1, card })
      .mockResolvedValue({ waiting: 0, card: null })
    vi.mocked(sortDeed).mockResolvedValue({ ok: true, next: 'staff' })
    render(<WorkDesk />)
    expect(await screen.findByText('Бан · Игрок')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /^Непонятно/ }))
    expect(await screen.findByText(/Карточка ушла сотруднику проекта/)).toBeTruthy()
    expect(screen.getByText(/Другие администраторы её уже не увидят/)).toBeTruthy()
    expect(sortDeed).toHaveBeenCalledWith(7, 'weak')
  })

  it('leaves arrow keys alone while someone types', async () => {
    vi.mocked(fetchDeedWork)
      .mockResolvedValueOnce({ waiting: 1, card })
      .mockResolvedValue({ waiting: 0, card: null })
    vi.mocked(sortDeed).mockResolvedValue({ ok: true })
    render(
      <>
        <input aria-label="поиск" />
        <WorkDesk />
      </>,
    )
    expect(await screen.findByText('Бан · Игрок')).toBeTruthy()
    fireEvent.keyDown(screen.getByLabelText('поиск'), { key: 'ArrowRight' })
    expect(sortDeed).not.toHaveBeenCalled()
    fireEvent.keyDown(window, { key: 'ArrowDown' })
    expect(await screen.findByText(EMPTY)).toBeTruthy()
    expect(sortDeed).toHaveBeenCalledWith(7, 'weak')
  })
})
