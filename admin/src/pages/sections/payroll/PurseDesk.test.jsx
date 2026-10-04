import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PurseDesk from './PurseDesk'
import { fetchDeedAnalytics, tuneDeedRates } from '../../../lib/adminClient'

vi.mock('../../../lib/adminClient', async (importOriginal) => ({
  ...(await importOriginal()),
  fetchDeedAnalytics: vi.fn(),
  tuneDeedRates: vi.fn(),
  isPanelPreviewMode: vi.fn(() => false),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const data = {
  purse: 100000,
  groups: 12,
  paid: {
    all: { all: 900, issue: 500, admin: 200, staff: 200 },
    week: { all: 120, issue: 80, admin: 20, staff: 20 },
    month: { all: 400, issue: 200, admin: 100, staff: 100 },
  },
  owed: { all: 40, issue: 20, admin: 10, staff: 10 },
  manualPaid: 15,
  days: [
    { day: '2026-10-03', issue: 10, admin: 4, staff: 4 },
    { day: '2026-10-04', issue: 0, admin: 0, staff: 0 },
  ],
  people: [
    { id: 4, name: 'Анна', issue: 0, admin: 200, staff: 0, paid: 200, owed: 40 },
  ],
  tune: { auto: true, note: 'Группы покрывают полную неделю. Кут уходит из групп только по кнопке «Выплатить».' },
  rates: [
    { actionType: 'ban', title: 'Баны', everyN: 100, rewardKut: 200, enabled: true, unit: '2', idealUnit: '2' },
    { actionType: 'check_admin', title: 'Проверки администраторов', everyN: 100, rewardKut: 40, enabled: true, unit: '0,4', idealUnit: '0,4' },
  ],
}

describe('PurseDesk', () => {
  it('shows salary taken from technical groups and who received it', async () => {
    vi.mocked(fetchDeedAnalytics).mockResolvedValue(data)
    render(<PurseDesk />)
    expect(await screen.findByText(/кут лежит в 12 технических группах/)).toBeTruthy()
    expect(screen.getByText(/кут ушёл из групп на зарплаты за 7 дней/)).toBeTruthy()
    expect(screen.getByText(/выдавшим 500, администраторам за проверки 200, сотрудникам за проверки 200/)).toBeTruthy()
    expect(screen.getByText(/За 30 дней из групп на зарплаты ушёл 400/)).toBeTruthy()
    expect(screen.getByText(/Ещё 15 кут вы отметили сами/)).toBeTruthy()
    expect(screen.getByText('Анна')).toBeTruthy()
    expect(screen.getByText(/Группы покрывают полную неделю/)).toBeTruthy()
    fireEvent.click(screen.getByRole('listitem', { name: /3 окт/ }))
    expect(screen.getByText(/Выдавшим 10, администраторам 4, сотрудникам 4/)).toBeTruthy()
  })

  it('asks the groups to retune the norms', async () => {
    vi.mocked(fetchDeedAnalytics).mockResolvedValue(data)
    vi.mocked(tuneDeedRates).mockResolvedValue({ ...data, tune: { ...data.tune, note: 'Нормы пересчитаны.' } })
    render(<PurseDesk />)
    expect(await screen.findByText('Баны')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Подстроить сейчас' }))
    expect(tuneDeedRates).toHaveBeenCalledWith({ auto: true, now: true })
    expect(await screen.findByText('Нормы пересчитаны.')).toBeTruthy()
  })
})
