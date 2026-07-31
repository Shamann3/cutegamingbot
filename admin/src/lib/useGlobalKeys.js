import { useEffect } from 'react'

/**
 * Глобальные горячие клавиши админки.
 *
 * Esc:
 *  1) закрыть открытый AdminSelect
 *  2) закрыть верхнюю модалку (кнопка отмены / backdrop)
 *  3) закрыть lightbox
 *  4) кастомный onEscape (мобильное меню и т.п.)
 *
 * Enter:
 *  — в модалке: подтвердить (primary/danger), в textarea — Ctrl/⌘+Enter
 *  — вне модалки: активировать сфокусированную кнопку
 */

function isTextEntry(el) {
  if (!el || el === document.body) return false
  if (el.isContentEditable) return true
  const tag = el.tagName
  if (tag === 'TEXTAREA' || tag === 'SELECT') return true
  if (tag !== 'INPUT') return false
  const type = String(el.type || 'text').toLowerCase()
  return !['button', 'submit', 'checkbox', 'radio', 'file', 'reset', 'image', 'hidden'].includes(type)
}

function topBackdrop() {
  const nodes = document.querySelectorAll('.admin-modal-backdrop')
  return nodes.length ? nodes[nodes.length - 1] : null
}

function findCancelButton(root) {
  return (
    root.querySelector('[data-modal-cancel]:not(:disabled)') ||
    root.querySelector('.admin-modal-actions [data-modal-cancel]:not(:disabled)') ||
    null
  )
}

function findConfirmButton(root) {
  const actions = root.querySelector('.admin-modal-actions')
  if (!actions) return null
  return (
    actions.querySelector('[data-modal-confirm]:not(:disabled)') ||
    actions.querySelector('.panel-users-btn-primary:not(:disabled)') ||
    actions.querySelector('.panel-users-btn-danger:not(:disabled)') ||
    [...actions.querySelectorAll('button:not(:disabled)')].at(-1) ||
    null
  )
}

export function useGlobalKeys({ onEscape, onEnter } = {}) {
  useEffect(() => {
    const handler = (e) => {
      if (e.isComposing) return

      if (e.key === 'Escape') {
        const openSelect = document.querySelector('.panel-select-open')
        if (openSelect) {
          e.preventDefault()
          openSelect.querySelector('.panel-select-trigger')?.click()
          return
        }

        const lightbox = document.querySelector('.img-lightbox')
        if (lightbox) {
          e.preventDefault()
          lightbox.querySelector('.img-lightbox-close')?.click()
          return
        }

        const backdrop = topBackdrop()
        if (backdrop) {
          e.preventDefault()
          const cancel = findCancelButton(backdrop)
          if (cancel) {
            cancel.click()
            return
          }
          // Клик по backdrop — стандартный onCancel у модалок
          backdrop.click()
          return
        }

        // Полноэкранная карта крафта
        const fsExit = document.querySelector('[data-craftmap-fs-exit]')
        if (fsExit) {
          e.preventDefault()
          fsExit.click()
          return
        }

        onEscape?.()
        return
      }

      if (e.key !== 'Enter' || e.shiftKey || e.altKey) return

      const backdrop = topBackdrop()
      if (backdrop) {
        const active = document.activeElement
        const typing = isTextEntry(active) && backdrop.contains(active)

        if (typing) {
          // В многострочном поле — только Ctrl/⌘+Enter
          if (active.tagName === 'TEXTAREA' && !(e.ctrlKey || e.metaKey)) return
        } else if (active?.tagName === 'BUTTON' && backdrop.contains(active) && !active.disabled) {
          e.preventDefault()
          active.click()
          return
        }

        const confirm = findConfirmButton(backdrop)
        if (confirm) {
          e.preventDefault()
          confirm.click()
        }
        return
      }

      const focused = document.activeElement
      if (focused?.tagName === 'BUTTON' && !focused.disabled && !isTextEntry(focused)) {
        // Нативная активация кнопки по Enter уже есть; не дублируем.
        return
      }

      onEnter?.()
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onEscape, onEnter])
}
