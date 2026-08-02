import { fetchShopCatalog } from '../lib/shopClient'
import { fetchMarketCatalog } from '../lib/marketClient'
import { createDexResolver } from './dexResolve'

const CATALOG_PROBE_SIZE = 48

function itemKey(item) {
  return String(item?.id ?? item?.itemId ?? '').trim()
}

function matchesTarget(item, target, { allowFuzzyName = true } = {}) {
  const key = itemKey(item)
  if (!key) return false
  if (target.canonId && target.resolver.resolve(key) === target.canonId) {
    return true
  }
  if (target.canonId && key === target.canonId) {
    return true
  }
  if (!allowFuzzyName) return false
  const name = String(item?.name ?? '').trim().toLowerCase()
  const needle = String(target.name ?? '').trim().toLowerCase()
  if (!needle || !name) return false
  if (name === needle) return true
  // Не покупаем урожай по имени культуры («Дерево» → бревно):
  // fuzzy только для явных саженцев / совпадения с именем семени.
  const looksLikeSeed = /сажен|семеч|seed|🌱/i.test(name) || /сажен|семеч|seed/i.test(needle)
  if (!looksLikeSeed) return false
  return name.includes(needle) || needle.includes(name)
}

function pickMatch(items, target) {
  if (!items?.length) return null
  const byId = items.find((item) => matchesTarget(item, target, { allowFuzzyName: false }))
  if (byId) return byId
  // Без canonId — только точное имя; с canonId fuzzy лишь как запасной путь.
  if (!target.canonId) {
    return items.find((item) => matchesTarget(item, target, { allowFuzzyName: true })) ?? null
  }
  return items.find((item) => matchesTarget(item, target, { allowFuzzyName: true })) ?? null
}

function uniqueSearches(target) {
  const values = [target.name, target.searchQuery, target.canonId]
  return [...new Set(values.map((value) => String(value ?? '').trim()).filter(Boolean))]
}

async function probeShop(target) {
  for (const search of uniqueSearches(target)) {
    const data = await fetchShopCatalog({
      category: 'all',
      page: 0,
      search,
      pageSize: CATALOG_PROBE_SIZE,
    })
    const match = pickMatch(data.items ?? [], target)
    if (match && Number(match.remains ?? 0) > 0) {
      return { item: match, kut: Number(data.kut ?? 0) }
    }
  }
  return null
}

async function probeMarket(target) {
  for (const search of uniqueSearches(target)) {
    const data = await fetchMarketCatalog({
      category: 'all',
      page: 0,
      search,
      pageSize: CATALOG_PROBE_SIZE,
    })
    const match = pickMatch(data.items ?? [], target)
    if (match && Number(match.quantity ?? 0) > 0) {
      return { item: match, kut: Number(data.kut ?? 0) }
    }
  }
  return null
}

function buildTarget(target = {}) {
  const resolver = createDexResolver(target.itemCatalog ?? {}, target.farmItemIds ?? null)
  const itemId = target.itemId ? resolver.resolve(String(target.itemId)) : ''
  const name = String(
    target.name
    || (itemId ? resolver.catalogName(itemId, '') : '')
    || target.search
    || '',
  ).trim()
  const emoji = target.emoji || (itemId ? resolver.catalogEmoji(itemId, '📦') : '📦')
  const searchQuery = String(target.search || name || itemId).trim()

  return {
    resolver,
    canonId: itemId || '',
    name: name || searchQuery,
    emoji,
    searchQuery,
  }
}

function openShopPurchase(item, kut) {
  window.dispatchEvent(new CustomEvent('farm:open-shop-purchase', {
    detail: { item, kut },
  }))
}

function openMarketPurchase(item, kut) {
  window.dispatchEvent(new CustomEvent('farm:open-market-purchase', {
    detail: { item, kut },
  }))
}

function goToMarketSearch(ctx) {
  window.dispatchEvent(new CustomEvent('farm:go-to-market', {
    detail: {
      search: ctx.searchQuery,
      itemId: ctx.canonId,
      highlightOnly: true,
      source: 'guide',
    },
  }))
}

function showItemUnavailable(ctx) {
  window.dispatchEvent(new CustomEvent('farm:item-unavailable', {
    detail: {
      name: ctx.name,
      emoji: ctx.emoji,
      itemId: ctx.canonId,
    },
  }))
}

/**
 * Умный переход к покупке предмета:
 * 1) окно покупки в магазине, 2) окно покупки на бирже, 3) сообщение + поиск на бирже.
 */
export async function guideToItemPurchase(target = {}) {
  const ctx = buildTarget(target)

  try {
    const shopResult = await probeShop(ctx)
    if (shopResult) {
      openShopPurchase(shopResult.item, shopResult.kut)
      return { destination: 'shop', item: shopResult.item }
    }

    const marketResult = await probeMarket(ctx)
    if (marketResult) {
      openMarketPurchase(marketResult.item, marketResult.kut)
      return { destination: 'market', item: marketResult.item }
    }

    showItemUnavailable(ctx)
    goToMarketSearch(ctx)
    return { destination: 'none' }
  } catch {
    window.dispatchEvent(new CustomEvent('farm:go-to-shop', {
      detail: {
        search: ctx.searchQuery,
        itemId: ctx.canonId,
        highlightOnly: true,
        source: 'guide-fallback',
      },
    }))
    return { destination: 'shop-fallback' }
  }
}
