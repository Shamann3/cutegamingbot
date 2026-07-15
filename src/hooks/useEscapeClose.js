import { useEffect } from 'react'

export function useEscapeClose(isOpen, onClose, { enabled = true } = {}) {
  useEffect(() => {
    if (!isOpen || !enabled) return undefined

    const handleKeyDown = (event) => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      event.stopPropagation()
      onClose()
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, enabled, onClose])
}

/**
 * Enter подтверждает действие в модалке когда фокус не в input/textarea.
 * onConfirm вызывается только если enabled=true и нет активного input.
 */
export function useEnterConfirm(isOpen, onConfirm, { enabled = true } = {}) {
  useEffect(() => {
    if (!isOpen || !enabled) return undefined

    const handleKeyDown = (event) => {
      if (event.key !== 'Enter') return
      const tag = document.activeElement?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      event.preventDefault()
      onConfirm()
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, enabled, onConfirm])
}
