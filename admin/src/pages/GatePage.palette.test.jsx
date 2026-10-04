import { act, cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import GatePage from './GatePage'

const statusFlight = vi.hoisted(() => {
  const box = {
    current: Promise.resolve({}),
    resolve: () => {},
    reset() {
      box.current = new Promise((resolve) => {
        box.resolve = resolve
      })
    },
  }
  box.reset()
  return box
})

vi.mock('../lib/adminClient', () => ({
  fetchAdminAuthStatus: () => statusFlight.current,
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
  const onGroupEnter = vi.fn()
  const utils = render(
    <GatePage
      onStaffEnter={onStaffEnter}
      onStaffApply={onStaffApply}
      onGroupEnter={onGroupEnter}
      onGroupApply={() => {}}
    />,
  )
  const colorBtn = () => utils.container.querySelector('.gate-color-btn')
  const panel = () => utils.container.querySelector('.accent-picker-panel')
  const staffDoor = () => utils.container.querySelector('.gate-door')
  const groupDoor = () => utils.container.querySelectorAll('.gate-door')[1]
  return { ...utils, onStaffEnter, onStaffApply, onGroupEnter, colorBtn, panel, staffDoor, groupDoor }
}

describe('Палитра в меню выбора панели', () => {
  beforeEach(() => {
    statusFlight.reset()
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
      statusFlight.resolve({ groupCanEnter: true, isProjectCreator: false })
      await statusFlight.current
    })
    tap(g.staffDoor())
    expect(g.onStaffEnter.mock.calls.length + g.onStaffApply.mock.calls.length).toBe(1)
    expect(g.container.textContent).toContain('Дальше нужен ключ')
  })

  it('создателю обе двери открываются без ключа, даже если он нажал до сверки', async () => {
    const g = renderGate()
    tap(g.staffDoor())
    expect(g.onStaffEnter).not.toHaveBeenCalled()
    expect(g.container.textContent).not.toContain('Дальше нужен ключ')

    await act(async () => {
      statusFlight.resolve({
        isProjectCreator: true,
        staffCanEnter: true,
        groupCanEnter: true,
      })
      await statusFlight.current
    })

    expect(g.onStaffEnter).toHaveBeenCalledWith(expect.objectContaining({ isProjectCreator: true }))
    expect(g.container.textContent).toContain('Кабинет групп. Нажмите — откроется сразу.')
    expect(g.container.textContent).not.toContain('Дальше нужен ключ')

    tap(g.groupDoor())
    expect(g.onGroupEnter).toHaveBeenCalledWith(expect.objectContaining({ isProjectCreator: true }))
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
