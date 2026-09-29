function clamp(value, min, max) {
  if (max < min) return min
  return Math.min(max, Math.max(min, value))
}

function overlaps(a, b, gap = 0) {
  return !(
    a.right <= b.left - gap
    || a.left >= b.right + gap
    || a.bottom <= b.top - gap
    || a.top >= b.bottom + gap
  )
}

/** Рамка панели: под шапкой Telegram и над нижним доком. */
export function coachFrame(viewport, obstacles = {}) {
  const top = Math.max(12, Number(obstacles.chromeTop) || 0)
  const dockTop = obstacles.dockTop
  const bottom = dockTop != null && dockTop > top + 80 && dockTop < viewport.height
    ? Math.min(viewport.height - 12, dockTop - 12)
    : viewport.height - 12
  return {
    top,
    left: 12,
    right: Math.max(12 + 160, viewport.width - 12),
    bottom: Math.max(top + 120, bottom),
  }
}

/**
 * Карточка по центру экрана, затем сдвиг только если она закрывает подсветку.
 * Итог всегда внутри рамки панели.
 */
export function placeCoachCard({ viewport, frame, card, spot }) {
  const width = clamp(card.width, 160, Math.max(160, frame.right - frame.left))
  const maxHeight = Math.max(120, frame.bottom - frame.top)
  const height = Math.min(Math.max(80, card.height), maxHeight)
  let left = clamp(viewport.width / 2 - width / 2, frame.left, frame.right - width)
  let top = clamp(viewport.height / 2 - height / 2, frame.top, frame.bottom - height)

  if (spot && spot.width > 0 && spot.height > 0) {
    const spotBox = {
      left: spot.left,
      top: spot.top,
      right: spot.left + spot.width,
      bottom: spot.top + spot.height,
    }
    const rect = () => ({ left, top, right: left + width, bottom: top + height })
    if (overlaps(rect(), spotBox, 10)) {
      const below = spotBox.bottom + 14
      const above = spotBox.top - 14 - height
      const roomBelow = frame.bottom - (below + height)
      const roomAbove = above - frame.top
      if (roomBelow >= 0 || roomAbove >= 0) {
        top = roomBelow >= roomAbove ? below : above
        top = clamp(top, frame.top, frame.bottom - height)
      }
      if (overlaps(rect(), spotBox, 10)) {
        const rightSide = spotBox.right + 14
        const leftSide = spotBox.left - 14 - width
        if (rightSide + width <= frame.right) left = rightSide
        else if (leftSide >= frame.left) left = leftSide
        left = clamp(left, frame.left, frame.right - width)
      }
    }
  }

  return {
    top: Math.round(top),
    left: Math.round(left),
    width: Math.round(width),
    maxHeight: Math.round(maxHeight),
  }
}
