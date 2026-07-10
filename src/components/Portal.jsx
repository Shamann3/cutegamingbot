import { useLayoutEffect } from 'react'
import { createPortal } from 'react-dom'
import { acquireScrollLock, releaseScrollLock } from '../utils/scrollLock'

export default function Portal({ children, lockScroll = false }) {
  useLayoutEffect(() => {
    if (!lockScroll) return undefined

    acquireScrollLock()
    return () => {
      releaseScrollLock()
    }
  }, [lockScroll])

  if (typeof document === 'undefined') return null
  return createPortal(children, document.body)
}
