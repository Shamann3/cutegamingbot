import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import EntryRite from './EntryRite'

describe('EntryRite', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    window.matchMedia = vi.fn(() => ({ matches: false }))
    Object.defineProperty(navigator, 'hardwareConcurrency', { configurable: true, value: 8 })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('собирает шесть цифр, затем чинит ошибки и открывает вход', async () => {
    const onDone = vi.fn()
    const { container } = render(<EntryRite digits="482193" onDone={onDone} />)
    expect(container.querySelector('.rite-cipher').textContent).toBe('482193')
    expect(onDone).not.toHaveBeenCalled()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1180 + 460)
    })
    expect(screen.getByText('связь оборвана')).toBeTruthy()
    expect(container.querySelectorAll('.rite-faults li.is-healed')).toHaveLength(0)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(160 + 8 * 240 + 520)
    })
    expect(container.querySelectorAll('.rite-faults li.is-healed')).toHaveLength(8)
    expect(screen.getByText('вход разрешён')).toBeTruthy()
    expect(onDone).toHaveBeenCalledTimes(1)
  })

  it('без движения сразу показывает исправленный вход и заканчивает', async () => {
    window.matchMedia = vi.fn(() => ({ matches: true }))
    const onDone = vi.fn()
    const { container } = render(<EntryRite digits="482193" onDone={onDone} />)
    expect(container.querySelectorAll('.rite-faults li.is-healed')).toHaveLength(8)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(400)
    })
    expect(onDone).toHaveBeenCalledTimes(1)
  })
})