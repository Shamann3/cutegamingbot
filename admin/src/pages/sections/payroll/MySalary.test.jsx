import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import MySalary from './MySalary'
import KutRate from './KutRate'
import { claimDeed, fetchDeedMine } from '../../../lib/adminClient'

vi.mock('../../../lib/adminClient', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchDeedMine: vi.fn(),
  claimDeed: vi.fn(),
  isPanelPreviewMode: vi.fn(() => false),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const ban = {
  actionType: 'ban',
  title: 'Баны',
  everyN: 100,
  rewardKut: 200,
  purse: 'tech',
  confirmed: 37,
  into: 37,
  left: 63,
}

describe('MySalary', () => {
  it('says how many punishments are left before the sum', async () => {
    vi.mocked(fetchDeedMine).mockResolvedValue({
      lines: [ban],
      checksOpen: 2,
      payouts: [],
    })
    render(<MySalary />)
    expect(await screen.findByText('Ещё 63 бана — и 200 кут.')).toBeTruthy()
    expect(screen.getByText(/Проверок ждёт решения создателя: 2/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Забрать куты' })).toBeNull()
  })

  it('lets the person take a finished norm or write the creator', async () => {
    vi.mocked(fetchDeedMine)
      .mockResolvedValueOnce({
        lines: [{ ...ban, confirmed: 100, into: 0, left: 100 }],
        checksOpen: 0,
        payouts: [{ id: 3, status: 'owed', purse: 'tech', rewardKut: 200, actionLabel: 'Баны' }],
      })
      .mockResolvedValueOnce({ lines: [ban], checksOpen: 0, payouts: [] })
    vi.mocked(claimDeed).mockResolvedValue({ ok: true })
    render(<MySalary />)
    expect(await screen.findByRole('button', { name: 'Забрать куты' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Написать @JerichoCute' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Забрать куты' }))
    expect(await screen.findByText('200 кут уже на балансе.')).toBeTruthy()
    expect(claimDeed).toHaveBeenCalledWith(3)
  })

  it('hides the rate calculator from this page', async () => {
    vi.mocked(fetchDeedMine).mockResolvedValue({ lines: [], checksOpen: 0, payouts: [] })
    render(<MySalary />)
    expect(await screen.findByText(/ещё не включил оплату/)).toBeTruthy()
    expect(screen.queryByText('Сколько стоит кут')).toBeNull()
  })
})

describe('KutRate', () => {
  it('shows one kut in stars and dollars', () => {
    render(<KutRate />)
    expect(screen.getByText('1 звезда')).toBeTruthy()
    expect(screen.getByText('$0.013 после 30% Telegram')).toBeTruthy()
    expect(screen.getByText(/\$0\.019 до комиссии/)).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Сколько кут посчитать'), { target: { value: '10' } })
    expect(screen.getByText('10 звёзд')).toBeTruthy()
    expect(screen.getByText('$0.13 после 30% Telegram')).toBeTruthy()
  })
})
