import { useCallback, useEffect, useState } from 'react'
import { readStorage, writeStorage } from '../utils/safeStorage'

const STORAGE_KEY = 'cute_shop_favorites'

function readFavorites() {
  const raw = readStorage(STORAGE_KEY)
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.map(String) : []
  } catch {
    return []
  }
}

export function useShopFavorites() {
  const [favorites, setFavorites] = useState(readFavorites)

  const persist = useCallback((next) => {
    setFavorites(next)
    writeStorage(STORAGE_KEY, JSON.stringify(next))
  }, [])

  const isFavorite = useCallback(
    (itemId) => favorites.includes(String(itemId)),
    [favorites],
  )

  const toggleFavorite = useCallback((itemId) => {
    const id = String(itemId)
    setFavorites((prev) => {
      const next = prev.includes(id)
        ? prev.filter((entry) => entry !== id)
        : [...prev, id]
      writeStorage(STORAGE_KEY, JSON.stringify(next))
      return next
    })
  }, [])

  useEffect(() => {
    setFavorites(readFavorites())
  }, [])

  return { favorites, isFavorite, toggleFavorite, persist }
}
