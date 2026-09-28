import { act, cleanup, fireEvent, render, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PanelSidebar from './PanelSidebar'
import { useGlobalKeys } from '../lib/useGlobalKeys'

vi.mock('../lib/adminProfile', () => ({
  getAdminProfile: () => ({ displayName: 'Иэрихон', username: 'ierihon', photoUrl: '' }),
  getAdminInitials: () => 'И',
}))

vi.mock('../lib/telegramDissolve', () => ({
  telegramDissolve: () => Promise.resolve(),
}))

vi.mock('./SessionTimer', () => ({ default: () => null }))

const phone = { value: true }
vi.mock('../lib/useIsDesktop', () => ({
  useIsPhone: () => phone.value,
}))

const ACCENT = { hex: '#00b4ff', h: 197, s: 1, v: 1, glow: 100, id: 'custom' }

function tap(el) {
  fireEvent.pointerDown(el)
  fireEvent.mouseDown(el)
  fireEvent.pointerUp(el)
  fireEvent.mouseUp(el)
  fireEvent.click(el)
}

function renderSidebar() {
  const onClose = vi.fn()
  const onChangeDoor = vi.fn()
  const onAccentChange = vi.fn()
  const utils = render(
    <>
      <PanelSidebar
        sections={[]}
        activeSection="dashboard"
        onNavigate={() => {}}
        onLogout={() => {}}
        onChangeDoor={onChangeDoor}
        mobileOpen
        onClose={onClose}
        accent={ACCENT}
        onAccentChange={onAccentChange}
        role="owner"
      />
      <button type="button" data-testid="page">страница</button>
    </>,
  )
  const trigger = () => utils.container.querySelector('.panel-accent-trigger')
  const panel = () => document.body.querySelector('.accent-picker-panel')
  const openPalette = () => {
    tap(trigger())
    expect(panel()).not.toBeNull()
  }
  const changeDoor = () =>
    [...utils.container.querySelectorAll('button')].find((b) => b.textContent.includes('Сменить панель'))
  return { ...utils, onClose, onChangeDoor, trigger, panel, openPalette, changeDoor }
}

async function settle(ms = 250) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

describe.each([
  ['телефон', true],
  ['ПК', false],
])('Сайдбар и палитра цвета (%s)', (_label, isPhone) => {
  beforeEach(() => {
    phone.value = isPhone
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

  it('тап по сайдбару закрывает только палитру и ничего в нём не нажимает', async () => {
    const s = renderSidebar()
    s.openPalette()

    tap(s.changeDoor())
    await settle()

    expect(s.panel()).toBeNull()
    expect(s.onClose).not.toHaveBeenCalled()
    expect(s.onChangeDoor).not.toHaveBeenCalled()
  })

  it('после закрытия палитры сайдбар работает как обычно', async () => {
    const s = renderSidebar()
    s.openPalette()
    tap(s.changeDoor())
    await settle(600)

    tap(s.changeDoor())
    expect(s.onChangeDoor).toHaveBeenCalledTimes(1)
  })

  it('тап внутри палитры ничего не закрывает', async () => {
    const s = renderSidebar()
    s.openPalette()

    tap(s.panel().querySelector('input[type="range"]'))
    tap(s.panel())
    await settle()

    expect(s.panel()).not.toBeNull()
    expect(s.onClose).not.toHaveBeenCalled()
  })

  it('повторный тап по кнопке «Любой цвет» закрывает палитру', async () => {
    const s = renderSidebar()
    s.openPalette()
    tap(s.trigger())
    await settle()
    expect(s.panel()).toBeNull()
    expect(s.onClose).not.toHaveBeenCalled()
  })

  it('Escape закрывает палитру', async () => {
    const s = renderSidebar()
    s.openPalette()
    fireEvent.keyDown(window, { key: 'Escape' })
    await settle()
    expect(s.panel()).toBeNull()
  })

  it('затемнение под палитрой не перехватывает клики', () => {
    const s = renderSidebar()
    s.openPalette()
    const backdrop = document.body.querySelector('.accent-picker-backdrop')
    expect(backdrop).not.toBeNull()
    expect(backdrop.tagName).not.toBe('BUTTON')
  })

  if (isPhone) {
    it('тап мимо сайдбара закрывает и палитру, и сайдбар', async () => {
      const s = renderSidebar()
      s.openPalette()

      tap(s.getByTestId('page'))
      await settle()

      expect(s.onClose).toHaveBeenCalledTimes(1)
      expect(s.panel()).toBeNull()
    })
  }
})

describe('Escape при открытой палитре', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('не закрывает сайдбар, пока открыта палитра', () => {
    const onEscape = vi.fn()
    renderHook(() => useGlobalKeys({ onEscape }))
    const panel = document.createElement('div')
    panel.className = 'accent-picker-panel'
    document.body.appendChild(panel)

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onEscape).not.toHaveBeenCalled()

    panel.remove()
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onEscape).toHaveBeenCalledTimes(1)
  })

  it('встроенная палитра (меню выбора панели) Escape не блокирует', () => {
    const onEscape = vi.fn()
    renderHook(() => useGlobalKeys({ onEscape }))
    const panel = document.createElement('div')
    panel.className = 'accent-picker-panel is-inline'
    document.body.appendChild(panel)
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onEscape).toHaveBeenCalledTimes(1)
  })
})
