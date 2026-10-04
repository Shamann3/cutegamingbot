import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CreatorPay from './CreatorPay'
import {
  fetchDeedDone,
  fetchDeedQueue,
  fetchDeedReviewers,
  keepDeed,
  liftDeed,
  undoDeed,
} from '../../../lib/adminClient'

vi.mock('../../../lib/adminClient', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchDeedReviewers: vi.fn(),
  fetchDeedQueue: vi.fn(),
  fetchDeedDone: vi.fn(),
  keepDeed: vi.fn(),
  dropDeed: vi.fn(),
  undoDeed: vi.fn(),
  liftDeed: vi.fn(),
  rejectLiftDeed: vi.fn(),
  isPanelPreviewMode: vi.fn(() => false),
}))

vi.mock('../../../components/PhotoLook', () => ({
  default: () => <div>фото</div>,
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const anna = {
  id: 4,
  name: 'Анна',
  title: 'Модератор',
  reviewed: 12,
  clear: 7,
  wrong: 3,
  weak: 2,
  kept: 5,
  dropped: 1,
  waiting: 6,
  lastAt: null,
}

const totals = { admins: 1, reviewed: 12, clear: 7, wrong: 3, weak: 2, kept: 5, dropped: 1, waiting: 6 }

const card = {
  id: 9,
  actionLabel: 'Бан',
  targetName: 'Игрок',
  adminName: 'Пётр',
  sorterName: 'Анна',
  sortVerdict: 'clear',
  sortLabel: 'Подходит',
  unclearCount: 0,
  unclearNames: [],
  direct: false,
  createdAt: '2026-10-01T12:00:00Z',
  durationMinutes: 60,
  reason: 'Спам в чате',
  hasProof: false,
  chatTitle: 'Кьют',
  scopeLabel: 'одна группа',
  chain: [{ role: 'admin', id: 4, name: 'Анна', verdict: 'clear', label: 'Подходит' }],
  credits: [
    { role: 'issue', userId: 3, name: 'Пётр', payable: 'keep' },
    { role: 'admin', userId: 4, name: 'Анна', verdict: 'clear', payable: 'keep' },
  ],
  lift: null,
  reviewStatus: null,
}

beforeEach(() => {
  vi.mocked(fetchDeedReviewers).mockResolvedValue({ people: [anna], totals })
})

describe('CreatorPay', () => {
  it('shows how many punishments each administrator checked', async () => {
    vi.mocked(fetchDeedQueue).mockResolvedValue({ waiting: 1, card })
    render(<CreatorPay />)
    expect((await screen.findAllByText('Анна')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('В зарплату 5 · мимо 1 · ждут вас 6')).toHaveLength(2)
    expect(screen.getAllByText('Подходит 7')).toHaveLength(2)
    expect(screen.getAllByText('Неправильно 3')).toHaveLength(2)
    expect(screen.getAllByText('Непонятно 2')).toHaveLength(2)
    expect(screen.getByText('В списке 1 человек')).toBeTruthy()
    expect(screen.getByText('Бан · Игрок')).toBeTruthy()
    expect(screen.getByText('наказание ждёт вашего решения')).toBeTruthy()
    expect(screen.getByText('Анна (администратор): подходит').className).toContain('is-clear')
  })

  it('colours the two decisions', async () => {
    vi.mocked(fetchDeedQueue).mockResolvedValue({ waiting: 1, card })
    render(<CreatorPay />)
    expect(await screen.findByText('Бан · Игрок')).toBeTruthy()
    expect(screen.getByRole('button', { name: /^В зарплату/ }).className).toContain('is-clear')
    expect(screen.getByRole('button', { name: /^Мимо/ }).className).toContain('is-wrong')
  })

  it('accepts the card into salary and can focus one administrator', async () => {
    vi.mocked(fetchDeedQueue)
      .mockResolvedValueOnce({ waiting: 1, card })
      .mockResolvedValue({ waiting: 0, card: null })
    vi.mocked(keepDeed).mockResolvedValue({ ok: true })
    render(<CreatorPay />)
    expect(await screen.findByText('Бан · Игрок')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /тому, кто выдал/ }))
    expect(await screen.findByText('Сейчас решать нечего.')).toBeTruthy()
    expect(screen.getByText('В зарплату. Засчитано тем, у кого стояла галочка и чей ответ совпал.')).toBeTruthy()
    expect(keepDeed).toHaveBeenCalledWith(9, [
      { role: 'issue', userId: 3 },
      { role: 'admin', userId: 4 },
    ])
    await waitFor(() => expect(fetchDeedReviewers).toHaveBeenCalledTimes(2))

    fireEvent.click(screen.getByRole('button', { name: /Анна/ }))
    expect(await screen.findByText('Показаны только проверки: Анна.')).toBeTruthy()
    expect(await screen.findByText(/Нажмите «Все, кто проверяет»/)).toBeTruthy()
    expect(fetchDeedQueue).toHaveBeenCalledWith({ sorterId: 4 })
  })

  it('takes the last decision back', async () => {
    vi.mocked(fetchDeedQueue)
      .mockResolvedValueOnce({ waiting: 1, card })
      .mockResolvedValueOnce({ waiting: 0, card: null })
      .mockResolvedValue({ waiting: 1, card })
    vi.mocked(keepDeed).mockResolvedValue({ ok: true })
    vi.mocked(undoDeed).mockResolvedValue({ ok: true, status: 'kept' })
    render(<CreatorPay />)
    expect(await screen.findByText('Бан · Игрок')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /тому, кто выдал/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'Вернуть' }))
    expect(await screen.findByText('Решение отменено и убрано из зарплаты. Карточка снова перед вами.')).toBeTruthy()
    expect(undoDeed).toHaveBeenCalledWith(9)
    expect(await screen.findByText('Бан · Игрок')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Вернуть' })).toBeNull()
  })

  it('shows a weak answer as one closed step', async () => {
    vi.mocked(fetchDeedQueue).mockResolvedValue({
      waiting: 1,
      card: {
        ...card,
        chain: [{ role: 'admin', id: 5, name: 'Олег', verdict: 'weak', label: 'Непонятно' }],
        credits: [{ role: 'admin', userId: 5, name: 'Олег', verdict: 'weak', payable: 'never' }],
      },
    })
    render(<CreatorPay />)
    expect(await screen.findByText('Олег (администратор): непонятно')).toBeTruthy()
    expect(screen.getByText('Сотрудник проекта эту карточку не проверял.')).toBeTruthy()
    expect(screen.getByText(/В зарплату не входит/)).toBeTruthy()
  })

  it('says when nobody could check the card', async () => {
    vi.mocked(fetchDeedQueue).mockResolvedValue({
      waiting: 1,
      card: { ...card, chain: [], credits: [], sortVerdict: null, sortLabel: '', sorterName: '', direct: true },
    })
    render(<CreatorPay />)
    expect(await screen.findByText('Некому было проверить')).toBeTruthy()
    expect(screen.getByText(/Администратора и сотрудника на эту карточку не нашлось/)).toBeTruthy()
  })

  it('lets the creator lift a pending request without paying by swipe', async () => {
    vi.mocked(fetchDeedQueue).mockResolvedValue({
      waiting: 1,
      card: {
        ...card,
        chain: [
          { role: 'admin', id: 4, name: 'Анна', verdict: 'wrong', label: 'Наказание выдано неправильно' },
          { role: 'staff', id: 8, name: 'Игорь', verdict: 'wrong', label: 'Наказание выдано неправильно', liftAsk: true },
        ],
        lift: { status: 'pending', by: 'Игорь', canLift: true, blocked: '' },
      },
    })
    vi.mocked(liftDeed).mockResolvedValue({ ok: true })
    render(<CreatorPay />)
    expect(await screen.findByText('Заявка на разблокировку')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /^Разблокировать/ }))
    expect(await screen.findByText(/Наказание снято/)).toBeTruthy()
    expect(liftDeed).toHaveBeenCalledWith(9)
  })

  it('lists decided cards with who checked them', async () => {
    vi.mocked(fetchDeedQueue).mockResolvedValue({ waiting: 0, card: null })
    vi.mocked(fetchDeedDone).mockResolvedValue({
      items: [{
        id: 3,
        status: 'dropped',
        actionLabel: 'Мут',
        targetName: 'Вася',
        adminName: 'Пётр',
        sortVerdict: 'wrong',
        sortLabel: 'Наказание выдано неправильно',
        sorterName: 'Анна',
        chain: [{ role: 'admin', name: 'Анна', verdict: 'wrong', label: 'Наказание выдано неправильно' }],
        createdAt: '2026-10-01T12:00:00Z',
        reviewedAt: '2026-10-02T12:00:00Z',
        reason: 'флуд',
        hasProof: false,
      }],
    })
    render(<CreatorPay />)
    fireEvent.click(screen.getByRole('button', { name: 'Решённые' }))
    expect(await screen.findByText('Мут · Вася')).toBeTruthy()
    expect(screen.getByText('Не в зарплате', { selector: '.done-mark' })).toBeTruthy()
    expect(screen.getByText(/^Анна \(администратор\): наказание выдано неправильно · решено/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'В зарплате' }))
    await waitFor(() => expect(fetchDeedDone).toHaveBeenLastCalledWith({ sorterId: 0, status: 'kept' }))
  })

  it('explains how an administrator gets into the list', async () => {
    vi.mocked(fetchDeedReviewers).mockResolvedValue({ people: [], totals: { admins: 0 } })
    vi.mocked(fetchDeedQueue).mockResolvedValue({ waiting: 0, card: null })
    render(<CreatorPay />)
    expect(await screen.findByText(/Проверять пока некому/)).toBeTruthy()
    expect(screen.getByText(/Архив/)).toBeTruthy()
  })
})
