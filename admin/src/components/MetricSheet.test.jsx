import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MetricSheetProvider, MetricTile } from './MetricSheet'

const phone = { value: false }
vi.mock('../lib/useIsDesktop', () => ({
  useIsPhone: () => phone.value,
}))

const SPEC = {
  id: 'calls',
  title: 'Вызовы бота',
  value: '18 452',
  hint: 'сегодня · вчера: 16 020',
  current: 18452,
  previous: 16020,
  previousLabel: 'вчера',
  bars: [
    { label: 'День', value: 18452 },
    { label: 'Неделя', value: 9000 },
  ],
  action: { label: 'Открыть активность', run: vi.fn() },
}

function tap(el) {
  fireEvent.pointerDown(el)
  fireEvent.mouseDown(el)
  fireEvent.pointerUp(el)
  fireEvent.mouseUp(el)
  fireEvent.click(el)
}

function renderTile(spec = SPEC) {
  return render(
    <MetricSheetProvider>
      <MetricTile spec={spec}>цифра</MetricTile>
      <button type="button">под листом</button>
    </MetricSheetProvider>,
  )
}

describe('MetricSheet', () => {
  beforeEach(() => {
    phone.value = false
    vi.useFakeTimers()
    SPEC.action.run.mockClear()
  })

  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  it('на ПК лист открывается по центру', () => {
    renderTile()
    tap(screen.getByRole('button', { name: /цифра/ }))
    const sheet = screen.getByRole('dialog', { name: 'Вызовы бота' })
    expect(sheet.closest('.metric-sheet-root').classList.contains('is-desk')).toBe(true)
    expect(sheet.textContent).toContain('18 452')
    expect(sheet.textContent.replace(/\u00a0/g, ' ')).toContain('+2 432')
    expect(sheet.textContent).toContain('День')
  })

  it('на телефоне лист прижат к низу', () => {
    phone.value = true
    renderTile()
    tap(screen.getByRole('button', { name: /цифра/ }))
    expect(screen.getByRole('dialog').closest('.metric-sheet-root').classList.contains('is-phone')).toBe(true)
  })

  it('на телефоне провод вниз закрывает лист', async () => {
    phone.value = true
    renderTile()
    tap(screen.getByRole('button', { name: /цифра/ }))
    const sheet = screen.getByRole('dialog')
    fireEvent.pointerDown(sheet, { pointerId: 1, clientY: 40, button: 0 })
    fireEvent.pointerMove(sheet, { pointerId: 1, clientY: 220 })
    fireEvent.pointerUp(sheet, { pointerId: 1, clientY: 220 })
    expect(sheet.style.transform).toContain('translate3d')
    await act(async () => {
      await vi.advanceTimersByTimeAsync(400)
    })
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('короткий сдвиг оставляет лист открытым', async () => {
    phone.value = true
    renderTile()
    tap(screen.getByRole('button', { name: /цифра/ }))
    const sheet = screen.getByRole('dialog')
    fireEvent.pointerDown(sheet, { pointerId: 1, clientY: 40, button: 0 })
    fireEvent.pointerMove(sheet, { pointerId: 1, clientY: 70 })
    fireEvent.pointerUp(sheet, { pointerId: 1, clientY: 70 })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(400)
    })
    expect(screen.getByRole('dialog')).toBeTruthy()
  })

  it('тап мимо закрывает лист и не нажимает то, что под ним', async () => {
    renderTile()
    tap(screen.getByRole('button', { name: /цифра/ }))
    const under = screen.getByRole('button', { name: 'под листом' })
    const pressed = vi.fn()
    under.addEventListener('click', pressed)
    tap(under)
    expect(pressed).not.toHaveBeenCalled()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250)
    })
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('кнопка действия выполняет переход и закрывает лист', async () => {
    renderTile()
    tap(screen.getByRole('button', { name: /цифра/ }))
    tap(screen.getByRole('button', { name: 'Открыть активность' }))
    expect(SPEC.action.run).toHaveBeenCalledTimes(1)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250)
    })
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('Escape закрывает только лист', async () => {
    renderTile()
    tap(screen.getByRole('button', { name: /цифра/ }))
    fireEvent.keyDown(window, { key: 'Escape' })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250)
    })
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('наведение на столбец показывает этот фрагмент', () => {
    renderTile()
    tap(screen.getByRole('button', { name: /цифра/ }))
    fireEvent.mouseEnter(screen.getByRole('option', { name: 'Неделя' }))
    const text = screen.getByRole('dialog').textContent.replace(/\u00a0/g, ' ')
    expect(text).toContain('Неделя')
    expect(text).toContain('9 000')
    expect(text).toContain('% от суммы фрагментов')
  })

  it('без данных плитка не кликабельна', () => {
    render(
      <MetricSheetProvider>
        <MetricTile disabled spec={SPEC}>пусто</MetricTile>
      </MetricSheetProvider>,
    )
    expect(screen.queryByRole('button', { name: /пусто/ })).toBeNull()
    expect(screen.getByText('пусто')).toBeTruthy()
  })
})
