import { useEffect, useState } from 'react'

const POP_MIN_MS = 5000
const POP_MAX_MS = 10_000
const POP_DURATION_MS = 700

function motionAllowed() {
  if (typeof window === 'undefined') return true
  return !window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function hashDelay(id, maxMs = 3500) {
  let hash = 0
  const key = String(id)
  for (let i = 0; i < key.length; i += 1) {
    hash = (hash * 31 + key.charCodeAt(i)) >>> 0
  }
  return hash % maxMs
}

function randomGap() {
  return POP_MIN_MS + Math.floor(Math.random() * (POP_MAX_MS - POP_MIN_MS + 1))
}

export function useShopEmojiPop(itemId, enabled = true) {
  const [popping, setPopping] = useState(false)

  useEffect(() => {
    if (!enabled || !motionAllowed()) {
      setPopping(false)
      return undefined
    }

    let gapTimeoutId
    let popTimeoutId

    const schedulePop = () => {
      gapTimeoutId = window.setTimeout(() => {
        setPopping(true)
        popTimeoutId = window.setTimeout(() => {
          setPopping(false)
          schedulePop()
        }, POP_DURATION_MS)
      }, randomGap())
    }

    const startTimeoutId = window.setTimeout(schedulePop, hashDelay(itemId))

    return () => {
      window.clearTimeout(startTimeoutId)
      window.clearTimeout(gapTimeoutId)
      window.clearTimeout(popTimeoutId)
      setPopping(false)
    }
  }, [itemId, enabled])

  return popping
}
