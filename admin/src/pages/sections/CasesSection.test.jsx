import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import CasesSection from './CasesSection'
import { fetchCaseBoard, saveCasePrice, saveCaseRules, saveCaseStock } from '../../lib/adminClient'

vi.mock('../../lib/adminClient', () => ({
  fetchCaseBoard: vi.fn(),
  saveCaseRules: vi.fn(),
  saveCasePrice: vi.fn(),
  saveCaseStock: vi.fn(),
}))

const BOARD = {
  cases: [
    {
      id: 'small',
      name: 'Маленький кейс',
      emoji: '📦',
      max: 50,
      average: 18.5,
      bands: [
        { chance: 70, amount: 10 },
        { chance: 30, amount: 50 },
      ],
    },
  ],
}

describe('cases desk', () => {
  afterEach(() => cleanup())

  it('shows the ceiling and saves a real jackpot', async () => {
    vi.mocked(fetchCaseBoard).mockResolvedValue(BOARD)
    vi.mocked(saveCaseRules).mockResolvedValue({
      ...BOARD.cases[0],
      max: 40,
      bands: [
        { chance: 80, amount: 8 },
        { chance: 20, amount: 40 },
      ],
      average: 14.4,
    })
    render(<CasesSection />)
    expect(await screen.findByText(/В среднем/)).toBeTruthy()
    expect(screen.getByText('Маленькая сумма')).toBeTruthy()
    expect(screen.getByText('Потолок')).toBeTruthy()
    expect(screen.getByText(/Комиссии нет/)).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Потолок Маленький кейс'), { target: { value: '40' } })
    fireEvent.change(screen.getByLabelText('Приз 1 Маленький кейс'), { target: { value: '8' } })
    fireEvent.change(screen.getByLabelText('Шанс 1 Маленький кейс'), { target: { value: '80' } })
    expect(screen.getByLabelText('Шанс 2 Маленький кейс').value).toBe('20')
    expect(screen.getAllByText(/80 раз из 100/).length).toBeGreaterThan(0)
    fireEvent.change(screen.getByLabelText('Приз 2 Маленький кейс'), { target: { value: '40' } })
    fireEvent.change(screen.getByLabelText('Шанс 2 Маленький кейс'), { target: { value: '20' } })
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
    await vi.waitFor(() => expect(saveCaseRules).toHaveBeenCalledWith({
      id: 'small',
      max: 40,
      bands: [
        { chance: 80, amount: 8 },
        { chance: 20, amount: 40 },
      ],
    }))
  })

  it('saves the shop price and the pieces on sale', async () => {
    vi.mocked(fetchCaseBoard).mockResolvedValue({
      cases: [],
      items: [{ id: '4', name: 'Ключ', name1: 'key', emoji: '🔑', price: 30, remains: 52, missing: false }],
    })
    vi.mocked(saveCasePrice).mockResolvedValue({ id: '4', name: 'Ключ', price: 40 })
    vi.mocked(saveCaseStock).mockResolvedValue({ id: '4', name: 'Ключ', remains: 10 })
    render(<CasesSection />)
    const price = await screen.findByLabelText('Цена Ключ')
    fireEvent.change(price, { target: { value: '40' } })
    fireEvent.click(screen.getByRole('button', { name: 'Цена' }))
    await vi.waitFor(() => expect(saveCasePrice).toHaveBeenCalledWith({ id: 4, price: 40 }))
    await vi.waitFor(() => expect(screen.getByLabelText('Цена Ключ').value).toBe('40'))
    fireEvent.change(screen.getByLabelText('Количество Ключ'), { target: { value: '10' } })
    fireEvent.click(screen.getByRole('button', { name: 'Количество' }))
    await vi.waitFor(() => expect(saveCaseStock).toHaveBeenCalledWith({ id: 4, remains: 10 }))
  })

  it('shows who won and the technical cash desk', async () => {
    const onOpenUser = vi.fn()
    vi.mocked(fetchCaseBoard).mockResolvedValue({
      cases: [],
      items: [],
      fund: 0,
      funds: [{ id: '-1004324787050', name: 'Игры', balance: 0 }],
      stats: {
        opens: 2,
        paid: 80,
        best: 50,
        byCase: [],
        winners: [{ userId: 42, name: 'Ника', opens: 2, won: 80, best: 50 }],
        recent: [{ userId: 42, name: 'Ника', caseId: 'small', caseName: 'Маленький кейс', emoji: 'x', amount: 50, at: '2026-10-12T12:00:00Z' }],
      },
    })
    render(<CasesSection onOpenUser={onOpenUser} />)
    expect(await screen.findByText('Игры')).toBeTruthy()
    expect(screen.getByText(/временно недоступны/)).toBeTruthy()
    expect(screen.getAllByText('Ника').length).toBeGreaterThan(0)
    expect(screen.getByText('+50')).toBeTruthy()
    fireEvent.click(screen.getAllByRole('button', { name: 'Ника' })[0])
    expect(onOpenUser).toHaveBeenCalledWith(42)
  })
})
