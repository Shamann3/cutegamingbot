/**
 * Прогрев статистики главной — чистое ядро без сетевых зависимостей.
 *
 * Запускается на экране визуальной загрузки, чтобы к моменту входа в панель
 * цифры уже лежали в памяти. Основной источник — лёгкий /dashboard/live
 * (ровно то, что показывает главная), запасной — полный /dashboard/stats.
 * Ни одна функция наружу не бросает: главный экран не показывает ошибок.
 */

export const SNAPSHOT_MAX_AGE_MS = 30000

export function createDashboardPrefetch({
  fetchLive,
  fetchFull,
  now = () => Date.now(),
  maxAgeMs = SNAPSHOT_MAX_AGE_MS,
} = {}) {
  let pending = null
  let snapshot = null
  let snapshotAt = 0

  const isFresh = () => snapshot != null && now() - snapshotAt <= maxAgeMs

  const accept = (data) => {
    if (!data || typeof data !== 'object') return false
    snapshot = data
    snapshotAt = now()
    return true
  }

  const tryFetch = async (fetcher) => {
    if (typeof fetcher !== 'function') return false
    try {
      return accept(await fetcher())
    } catch {
      return false
    }
  }

  function prime() {
    if (pending) return pending
    if (isFresh()) return Promise.resolve(snapshot)
    pending = (async () => {
      const ok = (await tryFetch(fetchLive)) || (await tryFetch(fetchFull))
      return ok ? snapshot : null
    })().finally(() => {
      pending = null
    })
    return pending
  }

  /** Свежий прогретый снимок или null. */
  function read() {
    return isFresh() ? snapshot : null
  }

  /** Текущий прогрев (если идёт) или уже готовый снимок. Никогда не бросает. */
  function current() {
    if (pending) return pending
    return Promise.resolve(read())
  }

  /**
   * Ждёт данные не дольше timeoutMs. Если прогрев не был запущен — запускает.
   * Возвращает снимок или null по таймауту.
   */
  function waitFor(timeoutMs) {
    const fresh = read()
    if (fresh) return Promise.resolve(fresh)
    const job = prime()
    if (!(timeoutMs > 0)) return job
    return new Promise((resolve) => {
      const timer = setTimeout(() => resolve(read()), timeoutMs)
      job.then((value) => {
        clearTimeout(timer)
        resolve(value)
      })
    })
  }

  function reset() {
    pending = null
    snapshot = null
    snapshotAt = 0
  }

  return { prime, read, current, waitFor, reset }
}
