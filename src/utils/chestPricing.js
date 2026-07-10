import { MAX_OPEN, CHEST_BOT_USERNAME } from '../constants/chests'

export function clampCount(n) {
  const v = Math.floor(Number(n))
  if (!Number.isFinite(v)) return 1
  return Math.max(1, Math.min(v, MAX_OPEN))
}

export function totalStars(count, priceStars) {
  return clampCount(count) * Math.max(0, Math.floor(Number(priceStars) || 0))
}

export function buildChestStartPayload(count) {
  return `chest_${clampCount(count)}`
}

export function buildChestBotUrl(count) {
  const user = String(CHEST_BOT_USERNAME).replace(/^@/, '')
  return `https://t.me/${user}?start=${buildChestStartPayload(count)}`
}
