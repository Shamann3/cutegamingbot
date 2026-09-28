import { act, cleanup, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import EntranceSeal, {
  ENTRANCE_DATA_GRACE_MS,
  ENTRANCE_EXIT_MS,
  ENTRANCE_LOGIN_HOLD_MS,
} from './EntranceSeal'
import { waitForDashboardStats } from '../lib/dashboardPrefetch'

vi.mock('../lib/adminClient', () => ({
  hasTelegramInitData: () => false,
  isAdminSessionValid: () => true,
}))

vi.mock('../lib/dashboardPrefetch', () => ({
  waitForDashboardStats: vi.fn(),
}))

vi.mock('./MatrixRain', async () => {
  const { createElement } = await import('react')
  return {
    default: ({ paused }) => createElement('div', { 'data-testid': 'matrix', 'data-paused': String(paused) }),
  }
})

const SNAPSHOT = { usage: {}, players: 1 }

/** Как настоящий waitFor: без лимита — ждёт запрос, с лимитом — отпускает с null. */
function emulateWaitFor(job) {
  return (timeoutMs) => {
    if (!(timeoutMs > 0)) return job
    return new Promise((resolve) => {
      const timer = setTimeout(() => resolve(null), timeoutMs)
      job.then((value) => {
        clearTimeout(timer)
        resolve(value)
      })
    })
  }
}

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

describe('EntranceSeal', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    localStorage.clear()
    vi.mocked(waitForDashboardStats).mockReset()
  })

  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  it('после логина показывает матрицу и печать кода', async () => {
    vi.mocked(waitForDashboardStats).mockImplementation(emulateWaitFor(new Promise(() => {})))
    const { container, getByTestId } = render(<EntranceSeal variant="login" onFinished={() => {}} />)
    expect(getByTestId('matrix').dataset.paused).toBe('false')
    await advance(1500)
    expect(container.querySelector('.ent-trace').textContent).toContain('epsilon')
  })

  it('после логина уходит в панель только когда статистика готова', async () => {
    const job = deferred()
    vi.mocked(waitForDashboardStats).mockImplementation(emulateWaitFor(job.promise))
    const onFinished = vi.fn()
    const { container } = render(<EntranceSeal variant="login" onFinished={onFinished} />)

    await advance(ENTRANCE_LOGIN_HOLD_MS + ENTRANCE_EXIT_MS + 200)
    expect(onFinished).not.toHaveBeenCalled()
    expect(container.querySelector('.ent-trace').textContent).toContain('загрузка')

    await act(async () => {
      job.resolve(SNAPSHOT)
    })
    expect(container.querySelector('.ent-trace').textContent).toContain('ready')
    await advance(ENTRANCE_EXIT_MS + 50)
    expect(onFinished).toHaveBeenCalledTimes(1)
  })

  it('данные готовы заранее — не задерживает вход', async () => {
    vi.mocked(waitForDashboardStats).mockImplementation(emulateWaitFor(Promise.resolve(SNAPSHOT)))
    const onFinished = vi.fn()
    render(<EntranceSeal variant="login" onFinished={onFinished} />)

    await advance(ENTRANCE_LOGIN_HOLD_MS + ENTRANCE_EXIT_MS + 50)
    expect(onFinished).toHaveBeenCalledTimes(1)
  })

  it('статистика не пришла — входит по лимиту ожидания', async () => {
    vi.mocked(waitForDashboardStats).mockImplementation(emulateWaitFor(new Promise(() => {})))
    const onFinished = vi.fn()
    render(<EntranceSeal variant="login" onFinished={onFinished} />)

    await advance(ENTRANCE_LOGIN_HOLD_MS + ENTRANCE_DATA_GRACE_MS - 100)
    expect(onFinished).not.toHaveBeenCalled()

    await advance(ENTRANCE_EXIT_MS + 200)
    expect(onFinished).toHaveBeenCalledTimes(1)
  })

  it('заставка при открытии (boot) статистику не ждёт', async () => {
    const onFinished = vi.fn()
    render(<EntranceSeal variant="boot" onFinished={onFinished} />)

    expect(waitForDashboardStats).not.toHaveBeenCalled()
    await advance(ENTRANCE_LOGIN_HOLD_MS + ENTRANCE_EXIT_MS + 50)
    expect(onFinished).toHaveBeenCalledTimes(1)
  })
})
