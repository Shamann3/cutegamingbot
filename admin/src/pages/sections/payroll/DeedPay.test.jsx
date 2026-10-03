import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DeedMine } from './DeedPay'
import { fetchDeedMine } from '../../../lib/adminClient'

vi.mock('../../../lib/adminClient', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchDeedMine: vi.fn(),
  isPanelPreviewMode: vi.fn(() => false),
}))

afterEach(() => {
  cleanup()
})

function line(title, left, rewardKut = 200) {
  return {
    actionType: title,
    title,
    everyN: 100,
    rewardKut,
    purse: 'tech',
    enabled: true,
    confirmed: 100 - left,
    into: 100 - left,
    left,
  }
}

describe('DeedMine', () => {
  it('does not show a zero balance before the answer arrives', () => {
    vi.mocked(fetchDeedMine).mockReturnValue(new Promise(() => {}))
    render(<DeedMine />)
    expect(screen.getByText('Считаем засчитанные наказания…')).toBeTruthy()
    expect(screen.queryByText('0 кут')).toBeNull()
  })

  it('shows money already owed, and the next prize as a sentence', async () => {
    vi.mocked(fetchDeedMine).mockResolvedValue({
      lines: [line('Баны', 63, 200), line('Муты', 1, 80)],
      waiting: 2,
      dropped: 0,
      owedKut: 0,
      paidKut: 0,
      payouts: [],
    })
    render(<DeedMine />)
    expect(await screen.findByText('0 кут')).toBeTruthy()
    expect(screen.getByText(/Ещё 1 мут — и 80 кут/)).toBeTruthy()
    expect(screen.queryByText(/^200 кут$/)).toBeNull()
  })

  it('uses the owed amount once a milestone is waiting', async () => {
    vi.mocked(fetchDeedMine).mockResolvedValue({
      lines: [line('Баны', 100, 200)],
      waiting: 0,
      dropped: 0,
      owedKut: 200,
      paidKut: 0,
      payouts: [],
    })
    render(<DeedMine />)
    expect(await screen.findByText('200 кут')).toBeTruthy()
    expect(screen.getByText(/Эта сумма уже набрана/)).toBeTruthy()
  })

  it('declines ban counts in Russian', async () => {
    vi.mocked(fetchDeedMine).mockResolvedValue({
      lines: [line('Баны', 21, 200), line('Муты', 11, 80), line('Кики', 2, 60), line('Предупреждения', 5, 50)],
      waiting: 0,
      dropped: 0,
      owedKut: 0,
      paidKut: 0,
      payouts: [],
    })
    render(<DeedMine />)
    expect(await screen.findByText(/Ещё 2 кика — и 60 кут/)).toBeTruthy()
    expect(screen.getByText('До 200 кут осталось 21 бан.')).toBeTruthy()
    expect(screen.getByText('До 80 кут осталось 11 мутов.')).toBeTruthy()
    expect(screen.getByText('До 50 кут осталось 5 предупреждений.')).toBeTruthy()
  })
})
