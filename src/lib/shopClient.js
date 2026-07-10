import { apiRequest } from './apiClient'

export function itemBuyPrice(item) {
  if (item.salePrice != null && item.salePrice > 0) {
    return item.salePrice
  }
  return item.price ?? 0
}

export function fetchShopCatalog({
  category = 'all',
  page = 0,
  search = '',
  priceFilter = 'all',
  sortBy = 'name',
  sortOrder = 'asc',
  pageSize = 8,
} = {}) {
  const params = new URLSearchParams({
    category,
    page: String(page),
    priceFilter,
    sortBy,
    sortOrder,
    pageSize: String(pageSize),
  })
  if (search.trim()) {
    params.set('search', search.trim())
  }
  return apiRequest(`/api/shop/catalog?${params}`)
}

export function buyShopItem(itemId, options = {}) {
  const {
    category = 'all',
    page = 0,
    search = '',
    quantity = 1,
    priceFilter = 'all',
    sortBy = 'name',
    sortOrder = 'asc',
    pageSize = 8,
  } = options

  return apiRequest('/api/shop/buy', {
    method: 'POST',
    body: {
      itemId,
      category,
      page,
      search: search.trim(),
      quantity,
      priceFilter,
      sortBy,
      sortOrder,
      pageSize,
    },
  })
}
