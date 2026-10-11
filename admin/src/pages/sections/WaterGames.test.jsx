import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import WaterGames from './WaterGames'
import { fetchWaterBoard, saveWaterStock } from '../../lib/adminClient'

vi.mock('../../lib/adminClient', () => ({
  fetchWaterBoard: vi.fn(),
  saveWaterPrice: vi.fn(),
  saveWaterStock: vi.fn(),
  saveWaterRules: vi.fn(),
}))

const BOARD = {
  totals: {},
  pours: [],
  soaked: [],
  pairs: [],
  recent: [],
  items: [
    { id: '336', name: 'Зонтик', name1: 'dryumbrella', emoji: '☂️', price: 60, remains: 12 },
  ],
}

describe('water games shop stock', () => {
  afterEach(() => cleanup())

  it('saves the shop quantity the creator typed', async () => {
    vi.mocked(fetchWaterBoard).mockResolvedValue(BOARD)
    vi.mocked(saveWaterStock).mockResolvedValue({ id: '336', name: 'Зонтик', remains: 40 })
    render(<WaterGames page />)
    const input = await screen.findByLabelText('Количество: Зонтик')
    expect(input.value).toBe('12')
    fireEvent.change(input, { target: { value: '40' } })
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить количество' }))
    await waitFor(() => {
      expect(saveWaterStock).toHaveBeenCalledWith({ id: 336, remains: 40 })
    })
    expect(await screen.findByText('Сейчас в продаже: 40 шт.')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Количество сохранено' }).disabled).toBe(true)
  })

  it('shows how much a splash takes from a given balance', async () => {
    vi.mocked(fetchWaterBoard).mockResolvedValue({
      ...BOARD,
      rules: { percentLow: 4, percentHigh: 8, shotCap: 1500, dayCap: 4000, poorBalance: 50 },
    })
    render(<WaterGames page />)
    expect(await screen.findByText('Заберёт от 40 до 80 кут')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Пример баланса'), { target: { value: '100000' } })
    expect(screen.getByText((text) => String(text).replace(/\s/g, '') === 'Заберёт1500кут')).toBeTruthy()
  })
})
