// Pure. No npm imports.
export function contentTabs(canUseMap) {
  const tabs = [
    { id: 'items', label: 'Предметы' },
    { id: 'crops', label: 'Культуры' },
    { id: 'craft', label: 'Крафт' },
  ]
  if (canUseMap) tabs.push({ id: 'map', label: '🗺 Карта' })
  tabs.push({ id: 'quests', label: 'Задания' })
  return tabs
}
