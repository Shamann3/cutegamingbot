import { apiRequest } from './apiClient'

export function fetchInventory() {
  return apiRequest('/api/inventory')
}

export function mapInventoryState(data) {
  return {
    kut: data?.kut ?? 0,
    items: data?.items ?? [],
    summary: data?.summary ?? { totalKinds: 0, totalCount: 0, groups: {} },
    axe: data?.axe ?? null,
    farmItemIds: data?.farmItemIds ?? null,
    itemCatalog: data?.itemCatalog ?? null,
  }
}
