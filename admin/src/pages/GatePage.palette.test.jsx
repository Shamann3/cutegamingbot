import { act, cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import GatePage from './GatePage'

vi.mock('../lib/adminClient', () => ({
  fetchAdminAuthStatus: () => new Promise(() => {}),
}))

vi.mock('../components/MatrixRain', () => ({ default: () => null }))

function tap(el) {
  fireEvent.pointerDown(el)
  fireEvent.mouseDown(el)
  fireEvent.pointerUp(el)
  fireEvent.mouseUp(el)
  fireEvent.click(el)
}

function renderGate() {
  const onStaffEnter = vi.fn()
  const onStaffApply = vi.fn()
  const utils = render(
    <GatePage
      onStaffEnter={onStaffEnter}
      onStaffApply={onStaffApply}
      onGroupEnter={() => {}}
      onGroupApply={() => {}}
    />,
  )
  const colorBtn = () => utils.container.querySelector('.gate-color-btn')
  const panel = () => utils.container.querySelector('.accent-picker-panel')
  const staffDoor = () => utils.container.querySelector('.gate-door')
  return { ...utils, onStaffEnter, onStaffApply, colorBtn, panel, staffDoor }
}

describe('Палитра в меню выбора панели', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null)
    globalThis.ResizeObserver = class {
      observe() {}
      disconnect() {}
    }
  })

  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  it('открывается и закрывается кнопкой', () => {
    const g = renderGate()
    tap(g.colorBtn())
    expect(g.panel()).not.toBeNull()
    tap(g.colorBtn())
    expect(g.panel()).toBeNull()
  })

  it('тап мимо палитры закрывает её', () => {
    const g = renderGate()
    tap(g.colorBtn())
    tap(g.container.querySelector('.gate-title'))
    expect(g.panel()).toBeNull()
  })

  it('тап по двери при открытой палитре только закрывает палитру', async () => {
    const g = renderGate()
    tap(g.colorBtn())
    tap(g.staffDoor())
    expect(g.panel()).toBeNull()
    expect(g.onStaffEnter).not.toHaveBeenCalled()
    expect(g.onStaffApply).not.toHaveBeenCalled()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(600)
    })
    tap(g.staffDoor())
    expect(g.onStaffEnter.mock.calls.length + g.onStaffApply.mock.calls.length).toBe(1)
  })

  it('тап внутри палитры её не закрывает', () => {
    const g = renderGate()
    tap(g.colorBtn())
    tap(g.panel().querySelector('input[type="range"]'))
    tap(g.panel())
    expect(g.panel()).not.toBeNull()
  })

  it('Escape закрывает палитру', () => {
    const g = renderGate()
    tap(g.colorBtn())
    act(() => {
      fireEvent.keyDown(window, { key: 'Escape' })
    })
    expect(g.panel()).toBeNull()
  })
})
