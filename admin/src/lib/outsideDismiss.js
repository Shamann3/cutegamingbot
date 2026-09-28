import { useEffect, useRef } from 'react'

const SWALLOW_AFTER_UP_MS = 400

/**
 * «Лёгкое закрытие» всплывающего слоя: тап/клик мимо него или Escape.
 *
 * - слушаем в capture-фазе на document — раньше любых stopPropagation;
 * - один жест = одно закрытие (pointerdown, а без PointerEvent — mouse/touch);
 * - swallowClick: клик, которым закрыли слой, не доходит до того, что под ним
 *   (не нажмётся пункт меню или дверь). Сам pointerdown при этом не глушим —
 *   другие слушатели (например, закрытие сайдбара) его получают.
 *
 * Возвращает функцию отписки.
 */
export function listenOutsideDismiss({ isInside, onDismiss, swallowClick = true, doc = document }) {
  const win = doc.defaultView || window
  let swallowCleanup = null
  let lastAt = -Infinity

  const stopSwallow = () => {
    swallowCleanup?.()
    swallowCleanup = null
  }

  const armSwallow = () => {
    stopSwallow()
    let timer = 0
    const eat = (event) => {
      event.preventDefault()
      event.stopPropagation()
      event.stopImmediatePropagation?.()
      stopSwallow()
    }
    const onUp = () => {
      win.clearTimeout(timer)
      timer = win.setTimeout(stopSwallow, SWALLOW_AFTER_UP_MS)
    }
    doc.addEventListener('click', eat, true)
    doc.addEventListener('pointerup', onUp, true)
    doc.addEventListener('mouseup', onUp, true)
    doc.addEventListener('touchend', onUp, true)
    // Жест превратился в прокрутку — клика не будет, глушить нечего.
    doc.addEventListener('pointercancel', stopSwallow, true)
    doc.addEventListener('touchcancel', stopSwallow, true)
    timer = win.setTimeout(stopSwallow, 4000)
    swallowCleanup = () => {
      win.clearTimeout(timer)
      doc.removeEventListener('click', eat, true)
      doc.removeEventListener('pointerup', onUp, true)
      doc.removeEventListener('mouseup', onUp, true)
      doc.removeEventListener('touchend', onUp, true)
      doc.removeEventListener('pointercancel', stopSwallow, true)
      doc.removeEventListener('touchcancel', stopSwallow, true)
    }
  }

  const onDown = (event) => {
    // mousedown после touchstart того же тапа — не второе закрытие.
    const now = Date.now()
    if (now - lastAt < 500) return
    const target = event.target
    if (target && isInside(target)) return
    lastAt = now
    if (swallowClick) armSwallow()
    onDismiss(event)
  }

  const onKey = (event) => {
    if (event.key === 'Escape') onDismiss(event)
  }

  const downEvents = 'PointerEvent' in win ? ['pointerdown'] : ['mousedown', 'touchstart']
  downEvents.forEach((type) => doc.addEventListener(type, onDown, true))
  win.addEventListener('keydown', onKey)

  return () => {
    downEvents.forEach((type) => doc.removeEventListener(type, onDown, true))
    win.removeEventListener('keydown', onKey)
    // Уже взведённое «съедание» клика доживает свой жест, иначе клик,
    // закрывший слой, провалится в элемент под ним.
  }
}

/** React-обёртка: активна, пока open. refs — узлы, клики по которым «внутри». */
export function useOutsideDismiss(open, refs, onDismiss, { swallowClick = true } = {}) {
  const onDismissRef = useRef(onDismiss)
  const refsRef = useRef(refs)
  onDismissRef.current = onDismiss
  refsRef.current = refs

  useEffect(() => {
    if (!open) return undefined
    return listenOutsideDismiss({
      swallowClick,
      isInside: (target) =>
        refsRef.current.some((ref) => {
          const node = ref?.current
          return node && typeof node.contains === 'function' && node.contains(target)
        }),
      onDismiss: (event) => onDismissRef.current?.(event),
    })
  }, [open, swallowClick])
}
