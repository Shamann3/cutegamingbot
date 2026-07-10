import { createDexResolver } from './dexResolve'

const CROP_KIND_LABELS = {
  tree: 'Дерево',
  tobacco: 'Табак',
}

function normalizeId(value) {
  return String(value ?? '').trim()
}

export function looksLikeRawItemId(value) {
  return /^\d{6,}$/.test(normalizeId(value))
}

function buildCtx(itemCatalog, farmItemIds) {
  return createDexResolver(itemCatalog, farmItemIds)
}

/** Определяет культуру (tree / tobacco) по id саженца на грядке или в инвентаре. */
export function inferCropKind(seedId, farmItemIds = null, itemCatalog = null) {
  const id = normalizeId(seedId)
  if (!id) return null
  if (id === 'tree') return 'tree'
  if (id === 'tobacco') return 'tobacco'

  const dex = buildCtx(itemCatalog, farmItemIds)
  const canon = dex.resolve(id)

  if (farmItemIds?.seed && dex.resolve(farmItemIds.seed) === canon) return 'tree'
  if (farmItemIds?.tobaccoSeed && dex.resolve(farmItemIds.tobaccoSeed) === canon) return 'tobacco'

  return null
}

export function seedIdsForCrop(crop, farmItemIds = null, itemCatalog = null) {
  const dex = buildCtx(itemCatalog, farmItemIds)
  const seedRef = crop?.seedId
  if (!seedRef) return []
  return dex.aliasesFor(seedRef)
}

export function findFarmCropByPlot(farmCrops, plot, farmItemIds = null, itemCatalog = null) {
  if (!farmCrops?.length) return null

  const cropKey = normalizeId(plot?.cropKey)
  if (cropKey) {
    const byKey = farmCrops.find((crop) => crop.key === cropKey)
    if (byKey) return byKey
  }

  const cropId = normalizeId(plot?.cropId)
  if (!cropId) return null

  const dex = buildCtx(itemCatalog, farmItemIds)
  const canon = dex.resolve(cropId)

  const direct = farmCrops.find((crop) => dex.resolve(crop.seedId) === canon)
  if (direct) return direct

  const kind = inferCropKind(cropId, farmItemIds, itemCatalog)
  if (kind) {
    return farmCrops.find((crop) => crop.key === kind) ?? null
  }

  return null
}

export function findFarmCrop(farmCrops, cropId, farmItemIds = null, itemCatalog = null) {
  if (!cropId || !farmCrops?.length) return null
  return findFarmCropByPlot(farmCrops, { cropId }, farmItemIds, itemCatalog)
}

export function cropDisplayLabel(crop, plot = null, itemCatalog = null) {
  const fromPlot = normalizeId(plot?.cropLabel)
  if (fromPlot && !looksLikeRawItemId(fromPlot)) return fromPlot

  const displayName = normalizeId(crop?.displayName)
  if (displayName && !looksLikeRawItemId(displayName)) return displayName

  const seedName = normalizeId(crop?.seedName)
  if (seedName && !looksLikeRawItemId(seedName)) return seedName

  if (crop?.seedId && itemCatalog) {
    const dex = createDexResolver(itemCatalog)
    const fromDex = dex.catalogName(crop.seedId)
    if (fromDex && !looksLikeRawItemId(fromDex)) return fromDex
  }

  if (crop?.key && CROP_KIND_LABELS[crop.key]) return CROP_KIND_LABELS[crop.key]

  const kind = inferCropKind(plot?.cropId, null, itemCatalog)
  if (kind && CROP_KIND_LABELS[kind]) return CROP_KIND_LABELS[kind]

  return 'Культура'
}
