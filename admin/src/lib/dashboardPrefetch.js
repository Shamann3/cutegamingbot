import { fetchDashboardLive, fetchDashboardStats } from './adminClient'
import { createDashboardPrefetch } from './dashboardPrefetchCore'

const prefetch = createDashboardPrefetch({
  fetchLive: fetchDashboardLive,
  fetchFull: fetchDashboardStats,
})

/** Запускает прогрев (повторные вызовы переиспользуют текущий запрос). */
export const primeDashboardStats = prefetch.prime

/** Свежий прогретый снимок или null. */
export const readDashboardSnapshot = prefetch.read

/** Текущий прогрев или готовый снимок. Никогда не бросает. */
export const awaitDashboardStats = prefetch.current

/** Ждёт данные не дольше timeoutMs; снимок или null. */
export const waitForDashboardStats = prefetch.waitFor
