import { act, cleanup, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import DashboardSection from './DashboardSection'
import { fetchDashboardLive, fetchDashboardStats } from '../../lib/adminClient'
import { awaitDashboardStats, readDashboardSnapshot } from '../../lib/dashboardPrefetch'

vi.mock('../../lib/adminClient', () => ({
  fetchDashboardLive: vi.fn(),
  fetchDashboardStats: vi.fn(),
}))

vi.mock('../../lib/dashboardPrefetch', () => ({
  awaitDashboardStats: vi.fn(),
  readDashboardSnapshot: vi.fn(),
}))

vi.mock('../../lib/useIsDesktop', () => ({
  useIsPhone: () => false,
}))

function pair(current, previous = 0) {
  const one = { current, previous }
  return { day: one, week: one, month: one, year: one }
}

function wager(current, lost, won) {
  const one = { current, previous: 0, lost, won }
  return { day: one, week: one, month: one, year: one }
}

const SNAPSHOT = {
  players: 4200,
  usage: {
    botEvents: pair(1234, 1000),
    allMessages: pair(5678),
    officialMessages: pair(910),
    gameWager: wager(3_500_000, 2_000_000, 1_500_000),
  },
}

async function flush(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

describe('DashboardSection', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.mocked(fetchDashboardLive).mockReset().mockResolvedValue(SNAPSHOT)
    vi.mocked(fetchDashboardStats).mockReset().mockResolvedValue(SNAPSHOT)
    vi.mocked(readDashboardSnapshot).mockReset()
    vi.mocked(awaitDashboardStats).mockReset()
  })

  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  it('прогретые данные видны с первого кадра — без «Идёт сбор данных»', async () => {
    vi.mocked(readDashboardSnapshot).mockReturnValue(SNAPSHOT)
    vi.mocked(awaitDashboardStats).mockResolvedValue(SNAPSHOT)
    const { queryAllByText, container } = render(<DashboardSection />)

    expect(queryAllByText('Идёт сбор данных')).toHaveLength(0)
    expect(container.querySelector('.dash-usage-split')).not.toBeNull()

    await flush(0)
    expect(fetchDashboardStats).not.toHaveBeenCalled()
  })

  it('прогретые данные — сразу 1 Гц поллинг лёгким /live', async () => {
    vi.mocked(readDashboardSnapshot).mockReturnValue(SNAPSHOT)
    vi.mocked(awaitDashboardStats).mockResolvedValue(SNAPSHOT)
    render(<DashboardSection />)

    await flush(250)
    expect(fetchDashboardLive).toHaveBeenCalledTimes(1)
    await flush(1000)
    expect(fetchDashboardLive).toHaveBeenCalledTimes(2)
    expect(fetchDashboardStats).not.toHaveBeenCalled()
  })

  it('без прогрева первым идёт лёгкий /live, а не тяжёлый снимок', async () => {
    vi.mocked(readDashboardSnapshot).mockReturnValue(null)
    vi.mocked(awaitDashboardStats).mockResolvedValue(null)
    const { queryAllByText } = render(<DashboardSection />)

    expect(queryAllByText('Идёт сбор данных').length).toBeGreaterThan(0)
    await flush(0)
    expect(fetchDashboardLive).toHaveBeenCalled()
    expect(fetchDashboardStats).not.toHaveBeenCalled()
    expect(queryAllByText('Идёт сбор данных')).toHaveLength(0)
  })

  it('если /live упал — берёт полный снимок', async () => {
    vi.mocked(readDashboardSnapshot).mockReturnValue(null)
    vi.mocked(awaitDashboardStats).mockResolvedValue(null)
    vi.mocked(fetchDashboardLive).mockRejectedValue(new Error('502'))
    const { queryAllByText } = render(<DashboardSection />)

    await flush(0)
    expect(fetchDashboardStats).toHaveBeenCalledTimes(1)
    expect(queryAllByText('Идёт сбор данных')).toHaveLength(0)
  })

  it('проиграно и выиграно — коротко, миллионы не распирают карточку', async () => {
    vi.mocked(readDashboardSnapshot).mockReturnValue(SNAPSHOT)
    vi.mocked(awaitDashboardStats).mockResolvedValue(SNAPSHOT)
    const { container } = render(<DashboardSection />)
    await flush(0)

    const values = [...container.querySelectorAll('.dash-usage-split-val')].map((el) =>
      el.textContent.replace(/[\u00a0\u202f]/g, ' '),
    )
    expect(values).toEqual(['2 млн', '1,5 млн'])
  })
})
