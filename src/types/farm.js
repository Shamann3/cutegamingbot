import { ITEM_IDS, ITEM_KEYS } from '../constants/itemIds'
import { inferCropKind, findFarmCrop, findFarmCropByPlot } from '../utils/cropMatch'

export { ITEM_IDS, ITEM_KEYS }
export { findFarmCrop, findFarmCropByPlot, inferCropKind }

export const PlotStatus = {
  EMPTY: 'EMPTY',
  GROWING: 'GROWING',
  READY: 'READY',
  WITHERED: 'WITHERED',
}

export const MAX_PLOTS = 8

/** Купить грядку #2 → 15 KUT, #3 → 30 … */
export function plotBuyPrice(plotId) {
  return (plotId - 1) * 15
}

export function isTreeCrop(cropId, farmItemIds, itemCatalog = null) {
  return inferCropKind(cropId, farmItemIds, itemCatalog) === 'tree'
    || cropId === 'tree'
}

export function isTobaccoCrop(cropId, farmItemIds, itemCatalog = null) {
  return inferCropKind(cropId, farmItemIds, itemCatalog) === 'tobacco'
    || cropId === 'tobacco'
}
