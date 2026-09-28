import { cleanup, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AccentAura from './AccentAura'

vi.mock('./MatrixRain', () => ({
  default: () => <div data-testid="rain" />,
}))

function media(matches) {
  window.matchMedia = vi.fn(() => ({
    matches,
    addEventListener() {},
    removeEventListener() {},
  }))
}

describe('AccentAura', () => {
  afterEach(() => {
    cleanup()
    localStorage.clear()
  })

  it('на обычном устройстве есть градиент и дождь', () => {
    media(false)
    Object.defineProperty(navigator, 'hardwareConcurrency', { configurable: true, value: 8 })
    const { container, getByTestId } = render(<AccentAura />)
    expect(container.querySelector('.accent-aura-wash')).not.toBeNull()
    expect(getByTestId('rain')).toBeTruthy()
  })

  it('при уменьшенном движении дождя нет, градиент остаётся', () => {
    media(true)
    const { container, queryByTestId } = render(<AccentAura />)
    expect(container.querySelector('.accent-aura-wash')).not.toBeNull()
    expect(queryByTestId('rain')).toBeNull()
  })

  it('в режиме оптимизации дождя нет', () => {
    media(false)
    localStorage.setItem('cf_admin_perf', '1')
    const { queryByTestId } = render(<AccentAura />)
    expect(queryByTestId('rain')).toBeNull()
  })
})
