import { fireEvent } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { listenOutsideDismiss } from './outsideDismiss'

/** Полный тап, как в браузере: down → up → click (и pointer, и mouse). */
function tap(el) {
  fireEvent.pointerDown(el)
  fireEvent.mouseDown(el)
  fireEvent.pointerUp(el)
  fireEvent.mouseUp(el)
  fireEvent.click(el)
}

describe('listenOutsideDismiss', () => {
  let layer
  let inner
  let outside
  let stop

  beforeEach(() => {
    vi.useFakeTimers()
    document.body.innerHTML = ''
    layer = document.createElement('div')
    inner = document.createElement('button')
    layer.appendChild(inner)
    outside = document.createElement('button')
    document.body.append(layer, outside)
  })

  afterEach(() => {
    stop?.()
    stop = null
    vi.useRealTimers()
  })

  const listen = (opts = {}) => {
    const onDismiss = vi.fn()
    stop = listenOutsideDismiss({ isInside: (t) => layer.contains(t), onDismiss, ...opts })
    return onDismiss
  }

  it('тап внутри слоя — не закрывает', () => {
    const onDismiss = listen()
    tap(inner)
    tap(layer)
    expect(onDismiss).not.toHaveBeenCalled()
  })

  it('тап мимо — закрывает ровно один раз за жест', () => {
    const onDismiss = listen()
    tap(outside)
    expect(onDismiss).toHaveBeenCalledTimes(1)
  })

  it('Escape закрывает', () => {
    const onDismiss = listen()
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onDismiss).toHaveBeenCalledTimes(1)
  })

  it('клик, которым закрыли слой, не нажимает то, что под ним', () => {
    listen()
    const pressed = vi.fn()
    outside.addEventListener('click', pressed)
    tap(outside)
    expect(pressed).not.toHaveBeenCalled()
  })

  it('следующий клик после закрытия проходит как обычно', () => {
    listen()
    const pressed = vi.fn()
    outside.addEventListener('click', pressed)
    tap(outside)
    stop()
    stop = null
    vi.advanceTimersByTime(500)
    tap(outside)
    expect(pressed).toHaveBeenCalledTimes(1)
  })

  it('съедается только один клик, даже если слой уже закрыт', () => {
    listen()
    const pressed = vi.fn()
    outside.addEventListener('click', pressed)
    fireEvent.pointerDown(outside)
    fireEvent.mouseDown(outside)
    stop()
    stop = null
    fireEvent.pointerUp(outside)
    fireEvent.click(outside)
    fireEvent.click(outside)
    expect(pressed).toHaveBeenCalledTimes(1)
  })

  it('жест ушёл в прокрутку — следующий клик не глушится', () => {
    listen()
    const pressed = vi.fn()
    outside.addEventListener('click', pressed)
    fireEvent.pointerDown(outside)
    fireEvent.pointerCancel(outside)
    fireEvent.click(outside)
    expect(pressed).toHaveBeenCalledTimes(1)
  })

  it('клик без парного up долго не висит', () => {
    listen()
    const pressed = vi.fn()
    outside.addEventListener('click', pressed)
    fireEvent.pointerDown(outside)
    vi.advanceTimersByTime(4100)
    fireEvent.click(outside)
    expect(pressed).toHaveBeenCalledTimes(1)
  })

  it('swallowClick: false — клик проходит насквозь', () => {
    listen({ swallowClick: false })
    const pressed = vi.fn()
    outside.addEventListener('click', pressed)
    tap(outside)
    expect(pressed).toHaveBeenCalledTimes(1)
  })

  it('другие слушатели pointerdown получают событие (сайдбар может закрыться сам)', () => {
    listen()
    const other = vi.fn()
    document.addEventListener('pointerdown', other, true)
    tap(outside)
    document.removeEventListener('pointerdown', other, true)
    expect(other).toHaveBeenCalledTimes(1)
  })

  it('после отписки ничего не закрывает', () => {
    const onDismiss = listen()
    stop()
    stop = null
    tap(outside)
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onDismiss).not.toHaveBeenCalled()
  })
})
