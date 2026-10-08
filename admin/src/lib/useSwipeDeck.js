import { useCallback, useLayoutEffect, useRef } from 'react'
import { armSaveCue, disarmSaveCue } from './cueSounds'
import { swipeAxis } from './gesture'

const SKIP = 'a, input, textarea, select, [data-noswipe]'

function paint(stage, drag, dx, threshold, live) {
  const power = Math.max(-1, Math.min(1, dx / threshold))
  if (stage) {
    stage.style.setProperty('--swipe', power.toFixed(3))
    stage.style.setProperty('--swipe-power', Math.abs(power).toFixed(3))
    stage.classList.toggle('is-live', live)
  }
  if (drag) {
    drag.style.transition = live ? 'none' : ''
    drag.style.transform = dx
      ? `translate3d(${dx}px, ${Math.abs(dx) * 0.04}px, 0) rotate(${dx / 22}deg)`
      : ''
  }
}

/**
 * Карточку тянут пальцем или мышью. Положение пишется прямо в DOM,
 * поэтому React не перерисовывает фото на каждом кадре.
 *
 * Направление решается по первым пикселям. Вертикальный жест отдаётся странице.
 * Горизонтальный держит страницу на месте: touchmove гасится до конца жеста.
 * pointer-событие прокрутку не отменяет, а touch-action меняется только
 * с нового касания, поэтому нужен свой touchmove без passive.
 * Касание без сдвига остаётся кликом.
 */
export default function useSwipeDeck({ onSwipe, disabled = false, threshold = 96, cardKey = null }) {
  const stageNode = useRef(null)
  const dragRef = useRef(null)
  const gesture = useRef(null)
  const touch = useRef(null)
  const swallow = useRef(false)
  const swipeRef = useRef(onSwipe)
  const disabledRef = useRef(disabled)
  const unbind = useRef(null)
  swipeRef.current = onSwipe
  disabledRef.current = disabled

  const reset = useCallback(() => {
    gesture.current = null
    paint(stageNode.current, dragRef.current, 0, threshold, false)
  }, [threshold])

  useLayoutEffect(() => {
    reset()
  }, [cardKey, reset])

  const stageRef = useCallback((node) => {
    if (stageNode.current === node) return
    unbind.current?.()
    unbind.current = null
    stageNode.current = node
    if (!node) return

    const start = (event) => {
      const point = event.touches?.[0]
      if (disabledRef.current || event.touches.length !== 1 || !point || event.target?.closest?.(SKIP)) {
        touch.current = null
        return
      }
      touch.current = { x: point.clientX, y: point.clientY, axis: null }
    }
    const move = (event) => {
      const t = touch.current
      if (!t) return
      const point = event.touches?.[0]
      if (event.touches.length !== 1 || !point) {
        touch.current = null
        return
      }
      if (!t.axis) {
        const axis = swipeAxis(point.clientX - t.x, point.clientY - t.y)
        if (!axis) return
        // Если страница уже поехала, событие не отменить — карточку не трогаем.
        t.axis = axis === 'x' && event.cancelable ? 'x' : 'y'
      }
      if (t.axis === 'x' && event.cancelable) event.preventDefault()
    }
    const end = () => {
      touch.current = null
    }

    node.addEventListener('touchstart', start, { passive: true })
    node.addEventListener('touchmove', move, { passive: false })
    node.addEventListener('touchend', end, { passive: true })
    node.addEventListener('touchcancel', end, { passive: true })
    unbind.current = () => {
      node.removeEventListener('touchstart', start)
      node.removeEventListener('touchmove', move)
      node.removeEventListener('touchend', end)
      node.removeEventListener('touchcancel', end)
    }
  }, [])

  const onPointerDown = useCallback((event) => {
    swallow.current = false
    if (disabled) return
    if (event.pointerType === 'mouse' && event.button !== 0) return
    if (event.target?.closest?.(SKIP)) return
    gesture.current = { id: event.pointerId, x: event.clientX, y: event.clientY, armed: false }
  }, [disabled])

  const onPointerMove = useCallback((event) => {
    const g = gesture.current
    if (!g || g.id !== event.pointerId) return
    const dx = event.clientX - g.x
    const dy = event.clientY - g.y
    if (!g.armed) {
      const axis = swipeAxis(dx, dy)
      if (!axis) return
      if (axis === 'y' || (event.pointerType === 'touch' && touch.current?.axis === 'y')) {
        gesture.current = null
        return
      }
      g.armed = true
      swallow.current = true
      try {
        event.currentTarget.setPointerCapture(event.pointerId)
      } catch {
        /* старый webview без захвата указателя: карточка всё равно едет за пальцем */
      }
    }
    if (event.cancelable) event.preventDefault()
    paint(stageNode.current, dragRef.current, dx, threshold, true)
  }, [threshold])

  const finish = useCallback((event, decide) => {
    const g = gesture.current
    if (!g || g.id !== event.pointerId) return
    gesture.current = null
    if (!g.armed) return
    const dx = event.clientX - g.x
    if (decide && Math.abs(dx) >= threshold) {
      stageNode.current?.classList.remove('is-live')
      if (dragRef.current) dragRef.current.style.transition = ''
      armSaveCue()
      if (swipeRef.current?.(dx > 0 ? 'right' : 'left')) return
      disarmSaveCue()
    }
    paint(stageNode.current, dragRef.current, 0, threshold, false)
  }, [threshold])

  const onPointerUp = useCallback((event) => finish(event, true), [finish])
  const onPointerCancel = useCallback((event) => finish(event, false), [finish])

  const onClickCapture = useCallback((event) => {
    if (!swallow.current) return
    swallow.current = false
    event.preventDefault()
    event.stopPropagation()
  }, [])

  const onDragStart = useCallback((event) => event.preventDefault(), [])

  return {
    stageRef,
    dragRef,
    reset,
    handlers: { onPointerDown, onPointerMove, onPointerUp, onPointerCancel, onClickCapture, onDragStart },
  }
}

const BLOCKED = 'input, textarea, select, [contenteditable="true"], .pay-people, .sec-tabs, [role="tablist"], [role="listbox"]'

/** Клавиша для колоды или null, если её нужно оставить странице. */
export function deckKey(event) {
  if (event.defaultPrevented || event.repeat) return null
  if (typeof document !== 'undefined' && document.querySelector('[aria-modal="true"]')) return null
  if (event.target?.closest?.(BLOCKED)) return null
  if ((event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey && event.code === 'KeyZ') return 'undo'
  if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return null
  if (event.key === 'ArrowLeft') return 'left'
  if (event.key === 'ArrowRight') return 'right'
  if (event.key === 'ArrowDown') return 'down'
  return null
}
