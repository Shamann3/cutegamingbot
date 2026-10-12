import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import CasesSection from './CasesSection'
import { fetchCaseBoard, saveCaseRules } from '../../lib/adminClient'

vi.mock('../../lib/adminClient', () => ({
  fetchCaseBoard: vi.fn(),
  saveCaseRules: vi.fn(),
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
    expect(screen.getByText(/Комиссии нет/)).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Потолок Маленький кейс'), { target: { value: '40' } })
    fireEvent.change(screen.getByLabelText('Приз 1 Маленький кейс'), { target: { value: '8' } })
    fireEvent.change(screen.getByLabelText('Шанс 1 Маленький кейс'), { target: { value: '80' } })
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
})
