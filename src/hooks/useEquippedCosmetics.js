import { useEffect, useState } from 'react'
import { fetchEquipped } from '../lib/chestClient'

// Надетая косметика по слотам. Один общий кэш на всё приложение: FarmBackground
// рендерится на каждой вкладке, поэтому без общего кэша было бы много запросов.
const EMPTY = { background: null, pet: null, plot: null, frame: null, title: null }

let cache = EMPTY
let inflight = null
const subscribers = new Set()

function load() {
  if (inflight) return inflight
  inflight = fetchEquipped()
    .then((data) => {
      cache = data || EMPTY
      subscribers.forEach((fn) => fn(cache))
      return cache
    })
    .catch(() => cache)
    .finally(() => { inflight = null })
  return inflight
}

if (typeof window !== 'undefined') {
  window.addEventListener('cosmetics:changed', () => load())
}

export function useEquippedCosmetics() {
  const [equipped, setEquipped] = useState(cache)

  useEffect(() => {
    subscribers.add(setEquipped)
    setEquipped(cache) // sync to the latest shared value on mount
    load()
    return () => { subscribers.delete(setEquipped) }
  }, [])

  return { equipped, refresh: load }
}
