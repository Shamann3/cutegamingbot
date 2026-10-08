/**
 * Нажатие в панели.
 *
 * Прокрутка не нажимает. Касание не считается нажатием, если:
 * — лента ещё ехала, когда палец коснулся: таким касанием ленту останавливают;
 * — во время касания лента под пальцем прокрутилась;
 * — палец заметно сдвинулся, пока был на экране.
 * Тогда click гасится, а свой не досылается.
 *
 * В Telegram WebView сжатие кнопки часто рисуется, а click не доходит:
 * палец оказывается за краем, пока кнопка уменьшается.
 * Если неподвижное касание началось на кнопке и отпущено рядом, а click не пришёл,
 * нажатие выполняется само. Повтор того же жеста в ту же долю секунды гасится.
 */

import { tapVerdict } from './gesture.js'

const PRESSABLE = [
  'button',
  '[role="button"]',
  '.e-tap',
  'a.auth-btn',
  'a.sec-btn',
  'a.elite-btn',
  'summary',
].join(', ')

const SLOP = 22
const MOVE_TOUCH = 16
const MOVE_MOUSE = 10
const STILL_MS = 160
const SCROLL_PX = 3
const DEDUPE_MS = 420
const SWALLOW_MS = 700

function pressable(target) {
  const node = target?.closest?.(PRESSABLE)
  if (!node) return null
  if (node.disabled || node.getAttribute('aria-disabled') === 'true') return null
  return node
}

function near(node, x, y) {
  const rect = node.getBoundingClientRect()
  return x >= rect.left - SLOP
    && x <= rect.right + SLOP
    && y >= rect.top - SLOP
    && y <= rect.bottom + SLOP
}

function scrollBox(target) {
  if (!target || target === document || target === window) return document.scrollingElement || document.documentElement
  if (target === document.body) return document.scrollingElement || document.documentElement
  return target
}

/** Когда лента под этим местом последний раз заметно двигалась. */
export function createScrollWatch(now = () => performance.now()) {
  const seen = new WeakMap()
  const note = (target) => {
    const box = scrollBox(target)
    if (!box) return
    const top = box.scrollTop || 0
    const left = box.scrollLeft || 0
    const last = seen.get(box)
    if (last && Math.abs(top - last.top) < SCROLL_PX && Math.abs(left - last.left) < SCROLL_PX) return
    seen.set(box, { top, left, at: now() })
  }
  const lastUnder = (node) => {
    let latest = seen.get(scrollBox(document))?.at || 0
    for (let el = node; el && el.nodeType === 1; el = el.parentNode) {
      const at = seen.get(el)?.at || 0
      if (at > latest) latest = at
    }
    return latest
  }
  return { note, lastUnder }
}

export function installPressCommit() {
  const watch = createScrollWatch()
  let press = null
  let letting = false
  let swallowUntil = 0

  const stamp = (node) => {
    node.dataset.pressStamp = String(Date.now())
  }

  const recent = (node) => {
    const at = Number(node?.dataset?.pressStamp || 0)
    return at > 0 && Date.now() - at < DEDUPE_MS
  }

  const swallow = () => {
    swallowUntil = performance.now() + SWALLOW_MS
  }

  document.addEventListener('scroll', (event) => watch.note(event.target), { capture: true, passive: true })

  document.addEventListener('pointerdown', (event) => {
    swallowUntil = 0
    if (event.button != null && event.button !== 0) {
      press = null
      return
    }
    const at = performance.now()
    const mouse = event.pointerType === 'mouse'
    press = {
      id: event.pointerId,
      kind: mouse ? 'mouse' : 'touch',
      target: event.target,
      node: pressable(event.target),
      x: event.clientX,
      y: event.clientY,
      at,
      slop: mouse ? MOVE_MOUSE : MOVE_TOUCH,
      moved: false,
      scrolledBefore: at - watch.lastUnder(event.target) < STILL_MS,
    }
  }, true)

  document.addEventListener('pointermove', (event) => {
    const p = press
    if (!p || p.moved || (p.id != null && event.pointerId !== p.id)) return
    if (Math.hypot(event.clientX - p.x, event.clientY - p.y) > p.slop) p.moved = true
  }, { capture: true, passive: true })

  document.addEventListener('click', (event) => {
    const node = pressable(event.target)
    if (letting) {
      if (node) stamp(node)
      return
    }
    if (swallowUntil && performance.now() < swallowUntil) {
      swallowUntil = 0
      event.preventDefault()
      event.stopPropagation()
      event.stopImmediatePropagation?.()
      return
    }
    if (!node) return
    if (node.dataset.pressHold === '1' && recent(node)) {
      event.preventDefault()
      event.stopPropagation()
      return
    }
    stamp(node)
  }, true)

  document.addEventListener('pointerup', (event) => {
    const p = press
    press = null
    if (!p) return
    if (p.id != null && event.pointerId != null && event.pointerId !== p.id) return
    if (!p.moved && Math.hypot(event.clientX - p.x, event.clientY - p.y) > p.slop) p.moved = true
    const verdict = tapVerdict({
      kind: p.kind,
      moved: p.moved,
      scrolledBefore: p.scrolledBefore,
      scrolledDuring: watch.lastUnder(p.target) > p.at,
    })
    if (verdict !== 'tap') {
      swallow()
      return
    }
    const node = p.node
    if (!node || !node.isConnected) return
    const inside = near(node, event.clientX, event.clientY)
    window.setTimeout(() => {
      if (!inside || !node.isConnected || recent(node)) return
      if (watch.lastUnder(node) > p.at) return
      node.dataset.pressHold = '1'
      letting = true
      try {
        stamp(node)
        node.click()
      } finally {
        letting = false
      }
      window.setTimeout(() => {
        if (node.dataset.pressHold === '1') delete node.dataset.pressHold
      }, DEDUPE_MS)
    }, 80)
  }, true)

  document.addEventListener('pointercancel', () => {
    // Браузер забрал жест под прокрутку. Click после этого не нужен.
    if (press) swallow()
    press = null
  }, true)
}
