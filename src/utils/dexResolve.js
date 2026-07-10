/**
 * Резолв предметов через itemCatalog (dex): id, name, name1, emoji.
 * Все alias-ключи в users.items сводятся к одному каноническому dex id.
 */

function registerAlias(map, alias, targetId) {
  const aliasKey = String(alias ?? '').trim()
  const id = String(targetId ?? '').trim()
  if (!aliasKey || !id) return
  map.set(aliasKey, id)
  map.set(aliasKey.toLowerCase(), id)
}

export function createDexResolver(itemCatalog = {}, farmItemIds = null) {
  const aliasToId = new Map()

  for (const entry of Object.values(itemCatalog || {})) {
    if (!entry?.id) continue
    const id = String(entry.id)
    registerAlias(aliasToId, id, id)
    if (entry.name) registerAlias(aliasToId, entry.name, id)
    if (entry.name1) registerAlias(aliasToId, entry.name1, id)
    if (entry.emoji) registerAlias(aliasToId, entry.emoji, id)
  }

  if (farmItemIds) {
    for (const ref of Object.values(farmItemIds)) {
      if (ref) registerAlias(aliasToId, ref, String(ref))
    }
  }

  const resolve = (ref) => {
    const key = String(ref ?? '').trim()
    if (!key) return key
    return aliasToId.get(key) ?? aliasToId.get(key.toLowerCase()) ?? key
  }

  const countIn = (items, ref) => {
    const target = resolve(ref)
    let total = 0
    for (const [rawKey, value] of Object.entries(items || {})) {
      if (resolve(rawKey) === target) total += Number(value) || 0
    }
    return total
  }

  const aliasesFor = (ref) => {
    const target = resolve(ref)
    const keys = new Set([target])
    for (const [alias, id] of aliasToId.entries()) {
      if (id === target) keys.add(alias)
    }
    return [...keys]
  }

  const catalogName = (ref, fallback = '') => {
    const id = resolve(ref)
    const entry = Object.values(itemCatalog || {}).find((e) => String(e?.id) === id)
    const name = String(entry?.name ?? '').trim()
    if (name && !/^\d{6,}$/.test(name)) return name
    return fallback
  }

  const catalogEmoji = (ref, fallback = '📦') => {
    const id = resolve(ref)
    const entry = Object.values(itemCatalog || {}).find((e) => String(e?.id) === id)
    return entry?.emoji || fallback
  }

  return { resolve, countIn, aliasesFor, catalogName, catalogEmoji, registerAlias }
}
