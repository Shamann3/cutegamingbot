import { useEffect } from 'react'

/**
 * Глобальные горячие клавиши для всей админки.
 * ESC закрывает модалки, дропдауны, мобильный сайдбар.
 * Enter подтверждает сфокусированную кнопку.
 */
export function useGlobalKeys({ onEscape, onEnter } = {}) {
  useEffect(() => {
    const handler = (e) => {
      // Не перехватываем если фокус в textarea/input (пусть пишут)
      const tag = document.activeElement?.tagName
      const isTyping = tag === 'TEXTAREA' || (tag === 'INPUT' && e.key !== 'Escape')

      if (e.key === 'Escape') {
        e.preventDefault()

        // 1. Закрыть открытый AdminSelect дропдаун
        const openSelect = document.querySelector('.panel-select-open')
        if (openSelect) {
          openSelect.querySelector('.panel-select-trigger')?.click()
          return
        }

        // 2. Закрыть верхний backdrop (модалка)
        const backdrops = document.querySelectorAll('.admin-modal-backdrop')
        if (backdrops.length > 0) {
          backdrops[backdrops.length - 1].click()
          return
        }

        // 3. Закрыть rules-gate
        const rulesGate = document.querySelector('.rules-gate-backdrop')
        if (rulesGate) {
          rulesGate.click()
          return
        }

        // 4. Кастомный колбэк (напр. закрыть мобильный сайдбар)
        onEscape?.()
        return
      }

      if (e.key === 'Enter' && !isTyping) {
        // Enter на сфокусированной кнопке нажимаем её
        const focused = document.activeElement
        if (focused?.tagName === 'BUTTON' && !focused.disabled) {
          focused.click()
          return
        }
        onEnter?.()
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onEscape, onEnter])
}
