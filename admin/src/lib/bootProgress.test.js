import { describe, expect, it } from 'vitest'
import {
  BOOT_BLEND_MS,
  BOOT_CREEP_MAX,
  BOOT_HOLD_CAP,
  blendProgress,
  bootIsComplete,
  bootProgressAt,
  bootProgressFrame,
} from './bootProgress'

const DURATION = 1600
const FRAME = 16

describe('bootProgressAt', () => {
  it('без ожидания идёт от 0 до 1 за duration', () => {
    expect(bootProgressAt(0, DURATION, false)).toBe(0)
    expect(bootProgressAt(DURATION, DURATION, false)).toBe(1)
    expect(bootProgressAt(DURATION * 3, DURATION, false)).toBe(1)
  })

  it('монотонно растёт', () => {
    let prev = -1
    for (let t = 0; t <= DURATION; t += FRAME) {
      const value = bootProgressAt(t, DURATION, false)
      expect(value).toBeGreaterThanOrEqual(prev)
      prev = value
    }
  })

  it('в ожидании данных не доходит до конца', () => {
    for (let t = 0; t <= 60_000; t += 250) {
      const value = bootProgressAt(t, DURATION, true)
      expect(value).toBeLessThanOrEqual(BOOT_CREEP_MAX)
      expect(bootIsComplete(value)).toBe(false)
      if (t <= DURATION) expect(value).toBeLessThanOrEqual(BOOT_HOLD_CAP)
    }
  })

  it('в ожидании данных не замирает: каждый шаг хоть немного вперёд', () => {
    let prev = bootProgressAt(DURATION, DURATION, true)
    for (let t = DURATION + 100; t <= DURATION + 6000; t += 100) {
      const value = bootProgressAt(t, DURATION, true)
      expect(value).toBeGreaterThan(prev)
      prev = value
    }
  })

  it('нулевая длительность — сразу конец', () => {
    expect(bootProgressAt(0, 0, false)).toBe(1)
  })
})

describe('blendProgress', () => {
  it('плавно ведёт from → target', () => {
    expect(blendProgress(0.5, 1, 0)).toBe(0.5)
    expect(blendProgress(0.5, 1, BOOT_BLEND_MS)).toBe(1)
    const mid = blendProgress(0.5, 1, BOOT_BLEND_MS / 2)
    expect(mid).toBeGreaterThan(0.5)
    expect(mid).toBeLessThan(1)
  })

  it('без длительности — сразу target', () => {
    expect(blendProgress(0.2, 0.9, 10, 0)).toBe(0.9)
  })
})

describe('bootProgressFrame', () => {
  function run({ needsData, readyAtMs, until = 12_000 }) {
    const frames = []
    let value = 0
    let readyAt = null
    let readyFrom = 0
    for (let t = 0; t <= until; t += FRAME) {
      if (readyAtMs != null && t >= readyAtMs && readyAt == null) {
        readyAt = t
        readyFrom = value
      }
      value = bootProgressFrame({ elapsed: t, duration: DURATION, needsData, readyAt, readyFrom })
      frames.push({ t, value })
      if (bootIsComplete(value)) break
    }
    return frames
  }

  function maxJump(frames) {
    let jump = 0
    for (let i = 1; i < frames.length; i += 1) {
      jump = Math.max(jump, Math.abs(frames[i].value - frames[i - 1].value))
    }
    return jump
  }

  function neverBack(frames) {
    return frames.every((frame, i) => i === 0 || frame.value >= frames[i - 1].value)
  }

  it('без данных завершается ровно по таймлайну', () => {
    const frames = run({ needsData: false })
    const last = frames.at(-1)
    expect(bootIsComplete(last.value)).toBe(true)
    expect(last.t).toBeGreaterThanOrEqual(DURATION * 0.95)
    expect(last.t).toBeLessThanOrEqual(DURATION + FRAME)
  })

  it('данные уже готовы — не медленнее обычного', () => {
    const frames = run({ needsData: true, readyAtMs: 0 })
    const last = frames.at(-1)
    expect(bootIsComplete(last.value)).toBe(true)
    expect(last.t).toBeLessThanOrEqual(DURATION + BOOT_BLEND_MS)
  })

  it('данные пришли поздно — ждёт, потом плавно доходит до конца', () => {
    const readyAtMs = 4000
    const frames = run({ needsData: true, readyAtMs })
    const before = frames.filter((frame) => frame.t < readyAtMs)
    expect(before.every((frame) => !bootIsComplete(frame.value))).toBe(true)
    const last = frames.at(-1)
    expect(bootIsComplete(last.value)).toBe(true)
    expect(last.t).toBeLessThanOrEqual(readyAtMs + BOOT_BLEND_MS + FRAME)
    expect(neverBack(frames)).toBe(true)
    expect(maxJump(frames)).toBeLessThan(0.08)
  })

  it('данные пришли посреди основной фазы — без рывков и без отката', () => {
    const frames = run({ needsData: true, readyAtMs: 700 })
    expect(neverBack(frames)).toBe(true)
    expect(maxJump(frames)).toBeLessThan(0.08)
    expect(bootIsComplete(frames.at(-1).value)).toBe(true)
  })

  it('данных нет совсем — не завершается сам (выход по лимиту снаружи)', () => {
    const frames = run({ needsData: true, readyAtMs: null, until: 20_000 })
    expect(bootIsComplete(frames.at(-1).value)).toBe(false)
    expect(neverBack(frames)).toBe(true)
  })
})
