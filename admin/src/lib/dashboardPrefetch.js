import { fetchDashboardStats } from './adminClient'

/**
 * Прогрев статистики главной: запускается на этапе визуальной загрузки,
 * чтобы к моменту входа в панель цифры уже были в памяти.
 */

const MAX_AGE_MS = 30000

let pending = null
let snapshot = null
let snapshotAt = 0

export function primeDashboardStats() {
  if (pending) return pending
  if (snapshot && Date.now() - snapshotAt < MAX_AGE_MS) {
    return Promise.resolve(snapshot)
  }
  pending = fetchDashboardStats()
    .then((data) => {
      if (data && typeof data === 'object') {
        snapshot = data
        snapshotAt = Date.now()
      }
      return snapshot
    })
    .catch(() => null)
    .finally(() => {
      pending = null
    })
  return pending
}

/** Свежий прогретый снимок или null. */
export function readDashboardSnapshot() {
  if (!snapshot) return null
  if (Date.now() - snapshotAt > MAX_AGE_MS) return null
  return snapshot
}

/** Ждёт текущий прогрев, если он идёт. Никогда не бросает. */
export function awaitDashboardStats() {
  if (pending) return pending
  return Promise.resolve(readDashboardSnapshot())
}
