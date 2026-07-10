import { useEffect, useState } from 'react'
import { shopLayoutForWidth } from '../utils/shopLayout'

const RESIZE_DEBOUNCE_MS = 120

export function useShopLayout() {
  const [layout, setLayout] = useState(() => shopLayoutForWidth(
    typeof window !== 'undefined' ? window.innerWidth : 0,
  ))

  useEffect(() => {
    let timeoutId = null

    const update = () => {
      setLayout(shopLayoutForWidth(window.innerWidth))
    }

    const onResize = () => {
      if (timeoutId) clearTimeout(timeoutId)
      timeoutId = setTimeout(update, RESIZE_DEBOUNCE_MS)
    }

    update()
    window.addEventListener('resize', onResize)
    return () => {
      if (timeoutId) clearTimeout(timeoutId)
      window.removeEventListener('resize', onResize)
    }
  }, [])

  return layout
}
