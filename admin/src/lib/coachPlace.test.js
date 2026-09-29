import { describe, expect, it } from 'vitest'
import { coachFrame, placeCoachCard } from './coachPlace'

const phone = { width: 390, height: 844 }

describe('placeCoachCard', () => {
  it('ставит карточку по центру и не выпускает её за рамку', () => {
    const frame = coachFrame(phone, { chromeTop: 28, dockTop: 770 })
    const card = placeCoachCard({
      viewport: phone,
      frame,
      card: { width: 360, height: 220 },
      spot: null,
    })
    expect(card.left).toBeGreaterThanOrEqual(frame.left)
    expect(card.left + card.width).toBeLessThanOrEqual(frame.right)
    expect(card.top).toBeGreaterThanOrEqual(frame.top)
    expect(card.top + 220).toBeLessThanOrEqual(frame.bottom)
    expect(card.left).toBe(Math.round((phone.width - card.width) / 2))
    expect(card.top).toBe(Math.round((phone.height - 220) / 2))
  })

  it('на телефоне остаётся выше дока', () => {
    const frame = coachFrame(phone, { chromeTop: 54, dockTop: 760 })
    const card = placeCoachCard({
      viewport: phone,
      frame,
      card: { width: 420, height: 280 },
      spot: { left: 16, top: 760, width: 358, height: 62 },
    })
    expect(card.top).toBeGreaterThanOrEqual(frame.top)
    expect(card.top).toBeLessThan(frame.bottom - 40)
    expect(card.maxHeight).toBe(Math.round(frame.bottom - frame.top))
    expect(card.left).toBe(frame.left)
    expect(card.left + card.width).toBeLessThanOrEqual(frame.right)
  })

  it('сдвигает карточку с подсветки, не выходя из панели', () => {
    const frame = coachFrame({ width: 1280, height: 800 }, { chromeTop: 0, dockTop: 736 })
    const spot = { left: 460, top: 280, width: 360, height: 180 }
    const card = placeCoachCard({
      viewport: { width: 1280, height: 800 },
      frame,
      card: { width: 380, height: 200 },
      spot,
    })
    const covers = !(
      card.left + card.width <= spot.left - 10
      || card.left >= spot.left + spot.width + 10
      || card.top >= spot.top + spot.height + 10
      || card.top + 200 <= spot.top - 10
    )
    expect(covers).toBe(false)
    expect(card.top).toBeGreaterThanOrEqual(frame.top)
    expect(card.left).toBeGreaterThanOrEqual(frame.left)
    expect(card.left + card.width).toBeLessThanOrEqual(frame.right)
    expect(card.top + 200).toBeLessThanOrEqual(frame.bottom)
  })
})
