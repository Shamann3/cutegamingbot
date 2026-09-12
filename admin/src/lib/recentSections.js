/** Недавние разделы панели — для быстрого доступа в mobile drawer. */

const STORAGE_KEY = 'epsilon.panel.recentSections'
const MAX_RECENT = 5

export function loadRecentSections() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const list = raw ? JSON.parse(raw) : []
    return Array.isArray(list) ? list.filter((id) => typeof id === 'string') : []
  } catch {
    return []
  }
}

export function pushRecentSection(sectionId) {
  if (!sectionId || typeof sectionId !== 'string') return loadRecentSections()
  try {
    const prev = loadRecentSections().filter((id) => id !== sectionId)
    const next = [sectionId, ...prev].slice(0, MAX_RECENT)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    return next
  } catch {
    return loadRecentSections()
  }
}
