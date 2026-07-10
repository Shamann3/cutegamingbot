import { useEffect } from 'react'

function isEditableTarget(target) {
  return target instanceof Element && Boolean(target.closest('input, textarea'))
}

function blockClipboard(event) {
  event.preventDefault()
}

function blockContextMenu(event) {
  event.preventDefault()
}

function blockDragStart(event) {
  if (isEditableTarget(event.target)) return
  event.preventDefault()
}

function blockSelectionStart(event) {
  if (isEditableTarget(event.target)) return
  event.preventDefault()
}

export function useContentProtection() {
  useEffect(() => {
    const options = { capture: true }

    document.addEventListener('copy', blockClipboard, options)
    document.addEventListener('cut', blockClipboard, options)
    document.addEventListener('contextmenu', blockContextMenu, options)
    document.addEventListener('dragstart', blockDragStart, options)
    document.addEventListener('selectstart', blockSelectionStart, options)

    const images = document.querySelectorAll('img')
    images.forEach((image) => {
      image.setAttribute('draggable', 'false')
    })

    return () => {
      document.removeEventListener('copy', blockClipboard, options)
      document.removeEventListener('cut', blockClipboard, options)
      document.removeEventListener('contextmenu', blockContextMenu, options)
      document.removeEventListener('dragstart', blockDragStart, options)
      document.removeEventListener('selectstart', blockSelectionStart, options)
    }
  }, [])
}
