/** Вкладки копии панели: только то, что включено у должности. */

export function previewAccessFromDefaults(map) {
  const sections = []
  const tabs = {}
  const source = map && typeof map === 'object' ? map : {}
  for (const [key, on] of Object.entries(source)) {
    const dot = key.indexOf('.')
    if (dot === -1) {
      if (on) sections.push(key)
      continue
    }
    const parent = key.slice(0, dot)
    const tab = key.slice(dot + 1)
    if (!tabs[parent]) tabs[parent] = []
    if (on) tabs[parent].push(tab)
  }
  return { sections, tabs }
}
