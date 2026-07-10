export const TREE_GROW_TIME_MS = 20 * 60 * 1000
export const TOBACCO_GROW_TIME_MS = 10 * 60 * 1000
/** @deprecated используйте ripeAt с сервера или growTimeMsForCrop */
export const GROW_TIME_MS = TREE_GROW_TIME_MS
export const WATER_INTERVAL_MS = 5 * 60 * 1000
/** @deprecated используйте WATER_INTERVAL_MS */
export const DRY_INTERVAL_MS = WATER_INTERVAL_MS
export const WILT_GRACE_MS = 120 * 1000
export const DRY_WARN_MS = 60 * 1000
export const WATER_ANIM_MS = 1800

export const GrowthStage = {
  SEED: 'seed',
  SPROUT: 'sprout',
  BUSH: 'bush',
  TREE: 'tree',
}

export function growTimeMsForCrop(seedOrCropId, farmCrops = []) {
  const crop = farmCrops.find(
    (entry) => entry.seedId === seedOrCropId || entry.key === seedOrCropId,
  )
  if (crop?.growSeconds) return crop.growSeconds * 1000
  if (seedOrCropId === 'tobacco') return TOBACCO_GROW_TIME_MS
  return TREE_GROW_TIME_MS
}

export function getGrowthStage(plantedAt, ripeAt, now = Date.now()) {
  if (!plantedAt || !ripeAt) return GrowthStage.SEED
  const total = ripeAt - plantedAt
  if (total <= 0) return GrowthStage.TREE
  const progress = Math.min(1, Math.max(0, (now - plantedAt) / total))
  if (progress < 0.2) return GrowthStage.SEED
  if (progress < 0.45) return GrowthStage.SPROUT
  if (progress < 0.75) return GrowthStage.BUSH
  return GrowthStage.TREE
}

export function getGrowthProgress(plantedAt, ripeAt, now = Date.now()) {
  if (!plantedAt || !ripeAt) return 0
  const total = ripeAt - plantedAt
  if (total <= 0) return 1
  return Math.min(1, Math.max(0, (now - plantedAt) / total))
}

export function isDrySoon(dryAt, needsWater, now = Date.now()) {
  if (!dryAt || needsWater) return false
  const remaining = dryAt - now
  return remaining <= DRY_WARN_MS && remaining > 0
}

export function isSoilMoist(dryAt, needsWater, now = Date.now()) {
  if (!dryAt || needsWater) return false
  const remaining = dryAt - now
  return remaining > DRY_WARN_MS
}
