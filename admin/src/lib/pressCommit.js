/**
 * Нажатие в Telegram WebView часто рисует сжатие кнопки и не доходит до click:
 * палец оказывается за краем, пока кнопка уменьшается.
 * Если жест начался на кнопке и отпущен рядом с ней, а click не пришёл,
 * нажатие выполняется само. Повтор того же жеста в ту же долю секунды гасится.
 */

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
const DEDUPE_MS = 420

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

export function installPressCommit() {
  let armed = null
  let pointerId = null
  let letting = false

  const stamp = (node) => {
    node.dataset.pressStamp = String(Date.now())
  }

  const recent = (node) => {
    const at = Number(node?.dataset?.pressStamp || 0)
    return at > 0 && Date.now() - at < DEDUPE_MS
  }

  document.addEventListener('pointerdown', (event) => {
    if (event.button != null && event.button !== 0) return
    const node = pressable(event.target)
    armed = node
    pointerId = node ? event.pointerId : null
  }, true)

  document.addEventListener('click', (event) => {
    const node = pressable(event.target)
    if (!node) return
    if (letting) {
      stamp(node)
      return
    }
    if (node.dataset.pressHold === '1' && recent(node)) {
      event.preventDefault()
      event.stopPropagation()
      return
    }
    stamp(node)
  }, true)

  document.addEventListener('pointerup', (event) => {
    const node = armed
    const id = pointerId
    armed = null
    pointerId = null
    if (!node || !node.isConnected) return
    if (id != null && event.pointerId != null && event.pointerId !== id) return
    const inside = near(node, event.clientX, event.clientY)
    window.setTimeout(() => {
      if (!inside || !node.isConnected || recent(node)) return
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
    armed = null
    pointerId = null
  }, true)
}
