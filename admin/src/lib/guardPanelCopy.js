import { isCopyableNode, isTextEntry, isTextEntryEvent } from './isTextEntry'

function stop(event) {
  event.preventDefault()
  event.stopPropagation()
}

function onCopyCut(event) {
  if (isTextEntryEvent(event)) return
  stop(event)
  try {
    event.clipboardData?.setData('text/plain', '')
    event.clipboardData?.setData('text/html', '')
  } catch {
    /* clipboardData может быть закрыт */
  }
}

function onSelectStart(event) {
  if (isTextEntryEvent(event)) return
  stop(event)
}

function onDragStart(event) {
  if (isTextEntryEvent(event)) return
  const sel = window.getSelection?.()
  if (sel && !sel.isCollapsed) stop(event)
}

function onKeyDown(event) {
  if (!(event.ctrlKey || event.metaKey)) return
  if (isTextEntryEvent(event)) return
  const key = String(event.key || '').toLowerCase()
  if (key === 'c' || key === 'x' || key === 'a' || key === 'insert') stop(event)
}

function onContextMenu(event) {
  if (isTextEntryEvent(event)) return
  stop(event)
}

function fieldFromNode(node) {
  if (!node) return null
  if (node.nodeType === 3) node = node.parentElement
  return node?.closest?.('input, textarea, select, [contenteditable="true"], [contenteditable=""], [data-copyable]') || null
}

function collapseForeignSelection() {
  const sel = window.getSelection?.()
  if (!sel || sel.isCollapsed) return
  const a = fieldFromNode(sel.anchorNode)
  const b = fieldFromNode(sel.focusNode)
  if ((isTextEntry(a) || isCopyableNode(a)) && (isTextEntry(b) || isCopyableNode(b))) return
  sel.removeAllRanges()
}

export function installPanelCopyGuard() {
  if (typeof document === 'undefined') return () => {}
  if (document.documentElement.dataset.noCopy === '1') {
    return () => {}
  }
  document.documentElement.dataset.noCopy = '1'

  document.addEventListener('copy', onCopyCut, true)
  document.addEventListener('cut', onCopyCut, true)
  document.addEventListener('selectstart', onSelectStart, true)
  document.addEventListener('dragstart', onDragStart, true)
  document.addEventListener('keydown', onKeyDown, true)
  document.addEventListener('contextmenu', onContextMenu, true)
  document.addEventListener('mouseup', collapseForeignSelection, true)
  document.addEventListener('touchend', collapseForeignSelection, true)

  return () => {
    document.removeEventListener('copy', onCopyCut, true)
    document.removeEventListener('cut', onCopyCut, true)
    document.removeEventListener('selectstart', onSelectStart, true)
    document.removeEventListener('dragstart', onDragStart, true)
    document.removeEventListener('keydown', onKeyDown, true)
    document.removeEventListener('contextmenu', onContextMenu, true)
    document.removeEventListener('mouseup', collapseForeignSelection, true)
    document.removeEventListener('touchend', collapseForeignSelection, true)
    delete document.documentElement.dataset.noCopy
  }
}
