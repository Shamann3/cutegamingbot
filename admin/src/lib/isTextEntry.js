const BLOCKED_INPUT = new Set([
  'button', 'submit', 'checkbox', 'radio', 'file', 'reset', 'image', 'hidden', 'range', 'color',
])

const FIELD_SEL = 'input, textarea, select, [contenteditable="true"], [contenteditable=""]'

export function isTextEntry(el) {
  if (!el) return false
  if (el.nodeType === 3) el = el.parentElement
  if (!el || el === document.body) return false
  if (el.isContentEditable) return true
  const tag = el.tagName
  if (tag === 'TEXTAREA' || tag === 'SELECT') return true
  if (tag !== 'INPUT') return false
  const type = String(el.type || 'text').toLowerCase()
  return !BLOCKED_INPUT.has(type)
}

export function isTextEntryEvent(event) {
  const target = event?.target
  const host = target?.closest?.(FIELD_SEL)
  return isTextEntry(target) || isTextEntry(host) || isTextEntry(document.activeElement)
}
