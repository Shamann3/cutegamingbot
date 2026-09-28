import { act, cleanup, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import MatrixRain from './MatrixRain'

function fakeContext() {
  return {
    fillText: vi.fn(),
    fillRect: vi.fn(),
    clearRect: vi.fn(),
    setTransform: vi.fn(),
    fillStyle: '',
    font: '',
    textBaseline: '',
  }
}

describe('MatrixRain', () => {
  let ctx

  beforeEach(() => {
    vi.useFakeTimers()
    ctx = fakeContext()
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(ctx)
    document.documentElement.style.setProperty('--e-accent-rgb', '12, 200, 90')
  })

  afterEach(() => {
    cleanup()
    vi.useRealTimers()
    document.documentElement.style.removeProperty('--e-accent-rgb')
  })

  it('пауза — ни canvas, ни работы', () => {
    const { container } = render(<MatrixRain paused />)
    expect(container.querySelector('canvas')).toBeNull()
    expect(ctx.fillText).not.toHaveBeenCalled()
  })

  it('без предпрогрева ничего не рисует до первого кадра', () => {
    render(<MatrixRain className="boot-matrix" />)
    expect(ctx.fillText).not.toHaveBeenCalled()
  })

  it('с предпрогревом дождь уже нарисован до первого кадра', () => {
    const { container } = render(<MatrixRain className="boot-matrix" prewarm={10} />)
    expect(container.querySelector('canvas.boot-matrix')).not.toBeNull()
    expect(ctx.fillRect).toHaveBeenCalledTimes(10)
    expect(ctx.fillText.mock.calls.length).toBeGreaterThan(0)
  })

  it('красит в цвет интерфейса', () => {
    render(<MatrixRain prewarm={1} />)
    expect(ctx.fillStyle).toContain('12, 200, 90')
  })

  it('кадры идут с ограничением fps', async () => {
    render(<MatrixRain fps={30} />)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    const frames = ctx.fillRect.mock.calls.length
    expect(frames).toBeGreaterThan(20)
    expect(frames).toBeLessThanOrEqual(31)
  })

  it('после размонтирования цикл останавливается', async () => {
    const { unmount } = render(<MatrixRain />)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200)
    })
    unmount()
    const before = ctx.fillRect.mock.calls.length
    await vi.advanceTimersByTimeAsync(1000)
    expect(ctx.fillRect.mock.calls.length).toBe(before)
  })
})
