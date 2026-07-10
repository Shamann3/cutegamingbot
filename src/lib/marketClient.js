import { apiRequest } from './apiClient'

const MARKET_COMMISSION_PERCENT_FALLBACK = 7

export function calcMarketCommission(gross, percent = MARKET_COMMISSION_PERCENT_FALLBACK) {
  const safeGross = Math.max(0, Math.floor(Number(gross) || 0))
  const safePercent = Math.max(0, Math.min(100, Math.floor(Number(percent) || 0)))
  return Math.floor(safeGross * safePercent / 100)
}

export function calcMarketSellerPayout(gross, percent = MARKET_COMMISSION_PERCENT_FALLBACK) {
  const safeGross = Math.max(0, Math.floor(Number(gross) || 0))
  return Math.max(0, safeGross - calcMarketCommission(safeGross, percent))
}

export function listingUnitPrice(item) {
  return item?.price ?? 0
}

function catalogParams({
  category = 'all',
  page = 0,
  search = '',
  priceFilter = 'all',
  sortBy = 'name',
  sortOrder = 'asc',
  pageSize = 8,
} = {}) {
  return {
    category,
    page,
    search: search.trim(),
    priceFilter,
    sortBy,
    sortOrder,
    pageSize,
  }
}

export function fetchMarketCatalog(options = {}) {
  const params = new URLSearchParams({
    category: options.category ?? 'all',
    page: String(options.page ?? 0),
    priceFilter: options.priceFilter ?? 'all',
    sortBy: options.sortBy ?? 'name',
    sortOrder: options.sortOrder ?? 'asc',
    pageSize: String(options.pageSize ?? 8),
  })
  if (options.search?.trim()) {
    params.set('search', options.search.trim())
  }
  return apiRequest(`/api/market/catalog?${params}`)
}

export function fetchMarketSellable() {
  return apiRequest('/api/market/sellable')
}

export function listMarketItem(itemId, price, options = {}) {
  return apiRequest('/api/market/list', {
    method: 'POST',
    body: {
      itemId,
      price,
      quantity: options.quantity ?? 1,
      ...catalogParams(options),
    },
  })
}

export function buyMarketListing(listingId, options = {}) {
  return apiRequest('/api/market/buy', {
    method: 'POST',
    body: {
      listingId: Number(listingId),
      quantity: options.quantity ?? 1,
      ...catalogParams(options),
    },
  })
}

export function cancelMarketListing(listingId, options = {}) {
  return apiRequest('/api/market/cancel', {
    method: 'POST',
    body: {
      listingId: Number(listingId),
      ...catalogParams(options),
    },
  })
}
