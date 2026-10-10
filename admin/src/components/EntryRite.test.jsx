import { act, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import EntryRite, { RITE_BURST_MS, RITE_FIELD_MS, RITE_GATHER_MS, RITE_TAIL_MS } from './EntryRite'

describe('EntryRite', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    window.matchMedia = vi.fn(() => ({ matches: false }))
    Object.defineProperty(navigator, 'hardwareConcurrency', { configurable: true, value: 8 })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('заполняет экран числами, собирает код и после вспышки открывает загрузку', async () => {
    const onDone = vi.fn()
    const { container } = render(<EntryRite digits="482193" onDone={onDone} />)
    const cells = container.querySelectorAll('.rite-cell')
    expect(cells.length).toBe(8 * 12)
    const keys = [...container.querySelectorAll('.rite-cell.is-key')].map((node) => node.textContent).join('')
    expect(keys).toBe('482193')
    expect(container.querySelector('.rite-note').textContent).toBe('Собираем ваш код')
    expect(onDone).not.toHaveBeenCalled()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(RITE_FIELD_MS)
    })
    expect(container.querySelector('.rite').className).toContain('is-gather')

    await act(async () => {
      await vi.advanceTimersByTimeAsync(RITE_GATHER_MS)
    })
    expect(container.querySelector('.rite').className).toContain('is-burst')
    expect(container.querySelector('.rite-note').textContent).toBe('Открываем загрузку')

    await act(async () => {
      await vi.advanceTimersByTimeAsync(RITE_BURST_MS + RITE_TAIL_MS)
    })
    expect(onDone).toHaveBeenCalledTimes(1)
  })

  it('без движения показывает собранный код и сразу открывает загрузку', async () => {
    window.matchMedia = vi.fn(() => ({ matches: true }))
    const onDone = vi.fn()
    const { container } = render(<EntryRite digits="482193" onDone={onDone} />)
    expect(container.querySelector('.rite').className).toContain('is-still')
    expect(container.querySelector('.rite-lock').textContent).toBe('482193')
    expect(container.querySelector('.rite-note').textContent).toBe('Открываем загрузку')
    await act(async () => {
      await vi.advanceTimersByTimeAsync(400)
    })
    expect(onDone).toHaveBeenCalledTimes(1)
  })
})