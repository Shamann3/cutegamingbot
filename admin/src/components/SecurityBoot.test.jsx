import { act, cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import SecurityBoot, { STATS_WAIT_CAP_MS } from './SecurityBoot'
import { waitForDashboardStats } from '../lib/dashboardPrefetch'

vi.mock('../lib/dashboardPrefetch', () => ({
  waitForDashboardStats: vi.fn(),
}))

vi.mock('./MatrixRain', async () => {
  const { createElement } = await import('react')
  return {
    default: ({ className, paused }) =>
      createElement('div', { 'data-testid': 'matrix', className, 'data-paused': String(paused) }),
  }
})

const SNAPSHOT = { usage: { botEvents: { day: { current: 1, previous: 0 } } }, players: 3 }
const STAFF_MS = 1600
const GROUP_MS = 1400

function deferred() {
  let resolve
  const promise = new Promise((res) => {
    resolve = res
  })
  return { promise, resolve }
}

async function advance(ms) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

function pctOf(container) {
  return Number(container.querySelector('.boot-pct').textContent)
}

function dataStep(container) {
  return container.querySelector('.boot-log-data')
}

describe('SecurityBoot', () => {
  let originalMatchMedia

  beforeEach(() => {
    vi.useFakeTimers()
    sessionStorage.clear()
    localStorage.clear()
    originalMatchMedia = window.matchMedia
    vi.mocked(waitForDashboardStats).mockReset()
  })

  afterEach(() => {
    cleanup()
    vi.useRealTimers()
    window.matchMedia = originalMatchMedia
  })

  it('на фоне идёт матрица', () => {
    vi.mocked(waitForDashboardStats).mockReturnValue(new Promise(() => {}))
    const { container } = render(<SecurityBoot kind="staff" onDone={() => {}} />)
    const matrix = container.querySelector('.boot-matrix')
    expect(matrix).not.toBeNull()
    expect(matrix.dataset.paused).toBe('false')
  })

  it('экран нельзя пропустить ни кликом, ни клавиатурой', async () => {
    vi.mocked(waitForDashboardStats).mockReturnValue(new Promise(() => {}))
    const onDone = vi.fn()
    const { container, queryByText } = render(<SecurityBoot kind="staff" onDone={onDone} />)
    const root = container.querySelector('.boot')

    expect(root.getAttribute('role')).toBe('status')
    expect(root.hasAttribute('tabindex')).toBe(false)
    expect(queryByText(/Нажмите/i)).toBeNull()

    fireEvent.click(root)
    fireEvent.pointerDown(root)
    fireEvent.keyDown(root, { key: 'Enter' })
    fireEvent.keyDown(root, { key: ' ' })
    fireEvent.keyDown(document, { key: 'Escape' })
    await advance(600)

    expect(onDone).not.toHaveBeenCalled()
  })

  it('панель сотрудника сразу запускает загрузку статистики с лимитом', () => {
    vi.mocked(waitForDashboardStats).mockReturnValue(new Promise(() => {}))
    render(<SecurityBoot kind="staff" onDone={() => {}} />)
    expect(waitForDashboardStats).toHaveBeenCalledTimes(1)
    expect(waitForDashboardStats).toHaveBeenCalledWith(STATS_WAIT_CAP_MS)
  })

  it('пока статистики нет — не уходит, а полоса продолжает ползти', async () => {
    const job = deferred()
    vi.mocked(waitForDashboardStats).mockReturnValue(job.promise)
    const onDone = vi.fn()
    const { container } = render(<SecurityBoot kind="staff" onDone={onDone} />)

    await advance(STAFF_MS + 400)
    const early = pctOf(container)
    expect(early).toBeGreaterThanOrEqual(90)
    expect(early).toBeLessThan(100)
    expect(dataStep(container).textContent).toContain('загрузка')

    await advance(2500)
    const later = pctOf(container)
    expect(later).toBeGreaterThan(early)
    expect(later).toBeLessThan(100)
    expect(onDone).not.toHaveBeenCalled()

    await act(async () => {
      job.resolve(SNAPSHOT)
    })
    await advance(600)

    expect(dataStep(container).textContent).toContain('готово')
    expect(pctOf(container)).toBe(100)
    expect(onDone).toHaveBeenCalledTimes(1)
  })

  it('данные уже в памяти — вход по обычному таймлайну', async () => {
    vi.mocked(waitForDashboardStats).mockResolvedValue(SNAPSHOT)
    const onDone = vi.fn()
    const { container } = render(<SecurityBoot kind="staff" onDone={onDone} />)

    await advance(STAFF_MS - 200)
    expect(onDone).not.toHaveBeenCalled()
    expect(dataStep(container).textContent).toContain('готово')

    await advance(600)
    expect(onDone).toHaveBeenCalledTimes(1)
  })

  it('статистика не успела к лимиту — входит, панель догрузит сама', async () => {
    vi.mocked(waitForDashboardStats).mockResolvedValue(null)
    const onDone = vi.fn()
    const { container } = render(<SecurityBoot kind="staff" onDone={onDone} />)

    await advance(STAFF_MS + 400)
    expect(dataStep(container).textContent).toContain('догрузим')
    expect(onDone).toHaveBeenCalledTimes(1)
  })

  it('даже если запрос повис навсегда — экран не зависает', async () => {
    vi.mocked(waitForDashboardStats).mockReturnValue(new Promise(() => {}))
    const onDone = vi.fn()
    render(<SecurityBoot kind="staff" onDone={onDone} />)

    await advance(STAFF_MS + STATS_WAIT_CAP_MS + 2100)
    expect(onDone).toHaveBeenCalledTimes(1)
  })

  it('панель группы не грузит статистику сотрудника', async () => {
    const onDone = vi.fn()
    const { container } = render(<SecurityBoot kind="group" onDone={onDone} />)

    expect(waitForDashboardStats).not.toHaveBeenCalled()
    expect(dataStep(container)).toBeNull()

    await advance(GROUP_MS + 400)
    expect(onDone).toHaveBeenCalledTimes(1)
  })

  it('onDone вызывается ровно один раз', async () => {
    vi.mocked(waitForDashboardStats).mockResolvedValue(SNAPSHOT)
    const onDone = vi.fn()
    render(<SecurityBoot kind="staff" onDone={onDone} />)

    await advance(STAFF_MS + STATS_WAIT_CAP_MS + 5000)
    expect(onDone).toHaveBeenCalledTimes(1)
  })

  it('при «уменьшить движение» — без матрицы, но статистику всё равно ждёт', async () => {
    window.matchMedia = vi.fn(() => ({
      matches: true,
      addEventListener() {},
      removeEventListener() {},
    }))
    const job = deferred()
    vi.mocked(waitForDashboardStats).mockReturnValue(job.promise)
    const onDone = vi.fn()
    const { container } = render(<SecurityBoot kind="staff" onDone={onDone} />)

    expect(container.querySelector('.boot').classList.contains('is-still')).toBe(true)
    expect(container.querySelector('.boot-matrix').dataset.paused).toBe('true')

    await advance(2000)
    expect(onDone).not.toHaveBeenCalled()

    await act(async () => {
      job.resolve(SNAPSHOT)
    })
    await advance(300)
    expect(onDone).toHaveBeenCalledTimes(1)
  })
})
