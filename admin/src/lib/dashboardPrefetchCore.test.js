import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createDashboardPrefetch, SNAPSHOT_MAX_AGE_MS } from './dashboardPrefetchCore'

const LIVE = { usage: { botEvents: { day: { current: 5, previous: 3 } } }, players: 10 }
const FULL = { usage: { botEvents: { day: { current: 7, previous: 3 } } }, players: 11 }

function deferred() {
  let resolve
  let reject
  const promise = new Promise((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function makeClock(start = 1_000_000) {
  let t = start
  return {
    now: () => t,
    advance: (ms) => {
      t += ms
    },
  }
}

describe('createDashboardPrefetch', () => {
  it('грузит лёгкий /live и не трогает тяжёлый снимок', async () => {
    const fetchLive = vi.fn().mockResolvedValue(LIVE)
    const fetchFull = vi.fn().mockResolvedValue(FULL)
    const prefetch = createDashboardPrefetch({ fetchLive, fetchFull })

    await expect(prefetch.prime()).resolves.toBe(LIVE)
    expect(fetchLive).toHaveBeenCalledTimes(1)
    expect(fetchFull).not.toHaveBeenCalled()
    expect(prefetch.read()).toBe(LIVE)
  })

  it('падает на полный снимок, если /live недоступен', async () => {
    const fetchLive = vi.fn().mockRejectedValue(new Error('502'))
    const fetchFull = vi.fn().mockResolvedValue(FULL)
    const prefetch = createDashboardPrefetch({ fetchLive, fetchFull })

    await expect(prefetch.prime()).resolves.toBe(FULL)
    expect(fetchFull).toHaveBeenCalledTimes(1)
  })

  it('не принимает пустой ответ за данные', async () => {
    const fetchLive = vi.fn().mockResolvedValue(null)
    const fetchFull = vi.fn().mockResolvedValue('oops')
    const prefetch = createDashboardPrefetch({ fetchLive, fetchFull })

    await expect(prefetch.prime()).resolves.toBeNull()
    expect(prefetch.read()).toBeNull()
  })

  it('никогда не бросает, даже если оба запроса упали', async () => {
    const prefetch = createDashboardPrefetch({
      fetchLive: () => Promise.reject(new Error('net')),
      fetchFull: () => {
        throw new Error('sync boom')
      },
    })
    await expect(prefetch.prime()).resolves.toBeNull()
    await expect(prefetch.current()).resolves.toBeNull()
    await expect(prefetch.waitFor(50)).resolves.toBeNull()
  })

  it('без фетчеров просто отдаёт null', async () => {
    const prefetch = createDashboardPrefetch()
    await expect(prefetch.prime()).resolves.toBeNull()
  })

  it('параллельные вызовы делят один запрос', async () => {
    const gate = deferred()
    const fetchLive = vi.fn(() => gate.promise)
    const prefetch = createDashboardPrefetch({ fetchLive })

    const a = prefetch.prime()
    const b = prefetch.prime()
    const c = prefetch.current()
    expect(a).toBe(b)
    expect(c).toBe(a)
    expect(fetchLive).toHaveBeenCalledTimes(1)

    gate.resolve(LIVE)
    await expect(Promise.all([a, b, c])).resolves.toEqual([LIVE, LIVE, LIVE])
  })

  it('свежий снимок отдаётся без повторного запроса', async () => {
    const fetchLive = vi.fn().mockResolvedValue(LIVE)
    const prefetch = createDashboardPrefetch({ fetchLive })
    await prefetch.prime()
    await prefetch.prime()
    await prefetch.waitFor(1000)
    expect(fetchLive).toHaveBeenCalledTimes(1)
  })

  it('устаревший снимок не выдаётся за свежий и перезапрашивается', async () => {
    const clock = makeClock()
    const fetchLive = vi.fn().mockResolvedValueOnce(LIVE).mockResolvedValueOnce(FULL)
    const prefetch = createDashboardPrefetch({ fetchLive, now: clock.now })

    await prefetch.prime()
    clock.advance(SNAPSHOT_MAX_AGE_MS)
    expect(prefetch.read()).toBe(LIVE)
    clock.advance(1)
    expect(prefetch.read()).toBeNull()

    await expect(prefetch.prime()).resolves.toBe(FULL)
    expect(fetchLive).toHaveBeenCalledTimes(2)
  })

  it('после сбоя следующий prime пробует снова', async () => {
    const fetchLive = vi.fn().mockRejectedValueOnce(new Error('net')).mockResolvedValueOnce(LIVE)
    const prefetch = createDashboardPrefetch({ fetchLive })
    await expect(prefetch.prime()).resolves.toBeNull()
    await expect(prefetch.prime()).resolves.toBe(LIVE)
  })

  it('current без прогрева отдаёт null и сам ничего не запрашивает', async () => {
    const fetchLive = vi.fn().mockResolvedValue(LIVE)
    const prefetch = createDashboardPrefetch({ fetchLive })
    await expect(prefetch.current()).resolves.toBeNull()
    expect(fetchLive).not.toHaveBeenCalled()
  })

  it('reset забывает снимок', async () => {
    const prefetch = createDashboardPrefetch({ fetchLive: async () => LIVE })
    await prefetch.prime()
    prefetch.reset()
    expect(prefetch.read()).toBeNull()
  })

  describe('waitFor', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    it('сразу отдаёт свежий снимок', async () => {
      const prefetch = createDashboardPrefetch({ fetchLive: async () => LIVE })
      await prefetch.prime()
      await expect(prefetch.waitFor(5000)).resolves.toBe(LIVE)
    })

    it('сам запускает прогрев и ждёт данные до таймаута', async () => {
      const gate = deferred()
      const fetchLive = vi.fn(() => gate.promise)
      const prefetch = createDashboardPrefetch({ fetchLive })

      const waiting = prefetch.waitFor(5000)
      expect(fetchLive).toHaveBeenCalledTimes(1)
      await vi.advanceTimersByTimeAsync(1200)
      gate.resolve(LIVE)
      await expect(waiting).resolves.toBe(LIVE)
    })

    it('по таймауту отпускает с null, а запрос продолжает жить', async () => {
      const gate = deferred()
      const prefetch = createDashboardPrefetch({ fetchLive: () => gate.promise })

      const waiting = prefetch.waitFor(6000)
      await vi.advanceTimersByTimeAsync(6000)
      await expect(waiting).resolves.toBeNull()

      gate.resolve(LIVE)
      await expect(prefetch.current()).resolves.toBe(LIVE)
      expect(prefetch.read()).toBe(LIVE)
    })

    it('без таймаута ждёт сам запрос', async () => {
      const gate = deferred()
      const prefetch = createDashboardPrefetch({ fetchLive: () => gate.promise })
      const waiting = prefetch.waitFor()
      await vi.advanceTimersByTimeAsync(60_000)
      gate.resolve(LIVE)
      await expect(waiting).resolves.toBe(LIVE)
    })
  })
})
