import { ITEM_IDS, MAX_PLOTS } from '../types/farm'
import { apiRequest } from './apiClient'
import { enrichSeedCounts } from '../utils/seedInventory'
import { createDexResolver } from '../utils/dexResolve'

function toTimestampMs(value) {
  if (value == null || value === '') return undefined
  if (typeof value === 'number' && Number.isFinite(value)) {
    if (value >= 1e9 && value < 1e12) return Math.round(value * 1000)
    return value
  }
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

function mapPlot(plot) {
  const mapped = {
    id: plot.id,
    status: plot.status,
    needsWater: plot.needsWater ?? false,
  }
  const plantedAt = toTimestampMs(plot.plantedAt)
  const ripeAt = toTimestampMs(plot.ripeAt)
  const dryAt = toTimestampMs(plot.dryAt)
  const wiltAt = toTimestampMs(plot.wiltAt)
  if (plantedAt != null) mapped.plantedAt = plantedAt
  if (ripeAt != null) mapped.ripeAt = ripeAt
  if (dryAt != null) mapped.dryAt = dryAt
  if (wiltAt != null) mapped.wiltAt = wiltAt
  if (plot.cropId) mapped.cropId = String(plot.cropId)
  if (plot.cropKey) mapped.cropKey = String(plot.cropKey)
  if (plot.cropLabel) mapped.cropLabel = String(plot.cropLabel)
  if (plot.autowaterActive) mapped.autowaterActive = true
  return mapped
}

export function mapFarmState(apiState) {
  const items = apiState.items ?? {}
  const itemCatalog = apiState.itemCatalog ?? {}
  const farmItemIds = apiState.farmItemIds ?? ITEM_IDS
  const dex = createDexResolver(itemCatalog, farmItemIds)
  const farmCrops = apiState.farmCrops ?? []
  const seedCount = apiState.seedCount ?? dex.countIn(items, farmItemIds.seed)
  const tobaccoSeedCount = apiState.tobaccoSeedCount ?? dex.countIn(items, farmItemIds.tobaccoSeed)
  const balanceBar = apiState.balanceBar ?? []
  const seedCounts = enrichSeedCounts({
    seedCounts: apiState.seedCounts ?? {},
    farmCrops,
    balanceBar,
    items,
    farmItemIds,
    itemCatalog,
    seedCount,
    tobaccoSeedCount,
  })

  return {
    kut: apiState.kut ?? 0,
    trees: apiState.inventory?.justtree ?? dex.countIn(items, farmItemIds.tree),
    items,
    itemsDisplay: apiState.itemsDisplay ?? null,
    itemCatalog,
    farmItemIds,
    seedCount,
    tobaccoSeedCount,
    seedCounts,
    farmCrops,
    balanceBar,
    axe: apiState.axe ?? null,
    waterCount: apiState.waterCount ?? dex.countIn(items, farmItemIds.water),
    autowaterCount: apiState.autowaterCount ?? dex.countIn(items, farmItemIds.autowater),
    ownedPlots: apiState.ownedPlots ?? apiState.plots?.length ?? 0,
    maxPlots: apiState.maxPlots ?? MAX_PLOTS,
    nextPlotId: apiState.nextPlotId ?? null,
    nextPlotPrice: apiState.nextPlotPrice ?? null,
    growSeconds: apiState.growSeconds ?? 20 * 60,
    plots: (apiState.plots ?? []).map(mapPlot),
    onboarding: apiState.onboarding ?? { done: false, active: false, step: 0 },
    seedEconomy: apiState.seedEconomy ?? null,
  }
}

export function fetchFarmState() {
  return apiRequest('/api/farm/state')
}

export function plantSeed(plotId, seedItemId) {
  return apiRequest('/api/farm/plant', { method: 'POST', body: { plotId, seedItemId } })
}

export function waterPlot(plotId, waterItemId = null) {
  const body = { plotId }
  if (waterItemId) body.waterItemId = waterItemId
  return apiRequest('/api/farm/water', { method: 'POST', body })
}

export function installAutowater(plotId) {
  return apiRequest('/api/farm/autowater', { method: 'POST', body: { plotId } })
}

export function harvestPlot(plotId) {
  return apiRequest('/api/farm/harvest', { method: 'POST', body: { plotId } })
}

export function clearPlot(plotId) {
  return apiRequest('/api/farm/clear', { method: 'POST', body: { plotId } })
}

export function buyPlot() {
  return apiRequest('/api/farm/buy-plot', { method: 'POST' })
}

export function claimDailySeed(seedItemId = null) {
  const body = seedItemId ? { seedItemId } : {}
  return apiRequest('/api/farm/claim-daily-seed', { method: 'POST', body })
}
