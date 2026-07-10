import { createDexResolver } from './dexResolve'
import { inferCropKind, seedIdsForCrop } from './cropMatch'

function countFromBalanceBar(crop, balanceBar) {
  if (!balanceBar?.length || !crop?.key) return 0
  const chip = balanceBar.find((c) => c.kind === 'crop' && c.id === crop.key)
  return chip ? Number(chip.value) || 0 : 0
}

function maxSeedCounts(seedCounts, aliasKeys) {
  let max = 0
  for (const key of aliasKeys) {
    max = Math.max(max, Number(seedCounts?.[key] ?? 0))
  }
  return max
}

/** Количество саженцев культуры (dex: id / name / emoji / legacy-ключ). */
export function cropSeedCount({
  crop,
  seedCounts = {},
  items = {},
  farmItemIds = null,
  balanceBar = [],
  itemCatalog = null,
}) {
  if (!crop) return 0

  const dex = createDexResolver(itemCatalog, farmItemIds)
  const aliasKeys = seedIdsForCrop(crop, farmItemIds, itemCatalog)
  const fromCounts = maxSeedCounts(seedCounts, aliasKeys)
  if (fromCounts > 0) return fromCounts

  const fromBar = countFromBalanceBar(crop, balanceBar)
  if (fromBar > 0) return fromBar

  return dex.countIn(items, crop.seedId)
}

export function isCropSeedAvailable(crop, ctx) {
  if (!crop) return false
  if (ctx.grantPlantSeed && (crop.key === 'tree' || crop.key === 'tobacco')) {
    return true
  }
  return cropSeedCount({ crop, ...ctx }) > 0
}

/** Культуры, для которых у игрока есть саженец прямо сейчас. */
export function listPlantableCrops(farmCrops, ctx) {
  if (!farmCrops?.length) return []
  return farmCrops.filter((crop) => isCropSeedAvailable(crop, ctx))
}

/** Дополняет seedCounts для всех alias-id каждой культуры. */
export function enrichSeedCounts({
  seedCounts = {},
  farmCrops = [],
  balanceBar = [],
  items = {},
  farmItemIds = null,
  itemCatalog = null,
  seedCount = 0,
  tobaccoSeedCount = 0,
}) {
  const dex = createDexResolver(itemCatalog, farmItemIds)
  const merged = { ...seedCounts }

  for (const crop of farmCrops) {
    const aliasKeys = seedIdsForCrop(crop, farmItemIds, itemCatalog)
    const fromBar = countFromBalanceBar(crop, balanceBar)
    const fromItems = dex.countIn(items, crop.seedId)
    const fromAliasCounts = maxSeedCounts(seedCounts, aliasKeys)

    let legacy = 0
    if (crop.key === 'tree') legacy = Number(seedCount) || 0
    if (crop.key === 'tobacco') legacy = Number(tobaccoSeedCount) || 0

    const value = Math.max(fromAliasCounts, fromBar, fromItems, legacy)
    if (value <= 0) continue

    const canon = dex.resolve(crop.seedId)
    merged[canon] = Math.max(Number(merged[canon] ?? 0), value)
    for (const key of aliasKeys) {
      merged[key] = Math.max(Number(merged[key] ?? 0), value)
    }
  }

  return merged
}

export { inferCropKind, seedIdsForCrop }
