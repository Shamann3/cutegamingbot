import { ITEM_IDS } from '../constants/itemIds'
import { cropSeedCount } from './seedInventory'

function countItem(items, itemId) {
  if (!items || !itemId) return 0
  return Number(items[itemId] ?? 0)
}

/** Собирает чипы панели баланса (fallback, если API не прислал balanceBar). */
export function buildBalanceBarChips({
  kut = 0,
  farmCrops = [],
  seedCounts = {},
  items = {},
  waterCount = 0,
  autowaterCount = 0,
  axe = null,
}) {
  const chips = [
    { kind: 'kut', id: 'kut', emoji: '💰', label: 'КУТ', value: Number(kut) || 0 },
  ]

  for (const crop of farmCrops) {
    const seedId = String(crop.seedId || '')
    chips.push({
      kind: 'crop',
      id: crop.key || seedId,
      emoji: crop.seedEmoji || '🌱',
      label: crop.displayName || crop.seedName || crop.key || 'Культура',
      value: cropSeedCount({
        crop,
        seedCounts,
        items,
      }),
    })
  }

  const seenWater = new Set()
  for (const crop of farmCrops) {
    const waterId = crop.waterItemId
    if (!waterId || seenWater.has(waterId)) continue
    seenWater.add(waterId)
    chips.push({
      kind: 'water',
      id: waterId,
      emoji: crop.waterEmoji || '💧',
      label: crop.waterName || 'Вода',
      value: countItem(items, waterId),
    })
  }
  if (!seenWater.size) {
    chips.push({
      kind: 'water',
      id: ITEM_IDS.WATER,
      emoji: '💧',
      label: 'Вода',
      value: Number(waterCount) || countItem(items, ITEM_IDS.WATER),
    })
  }

  const autowaterValue = countItem(items, ITEM_IDS.AUTOWATER)
  if (autowaterValue > 0) {
    chips.push({
      kind: 'autowater',
      id: ITEM_IDS.AUTOWATER,
      emoji: '🚰',
      label: 'Автополив',
      value: autowaterValue,
    })
  }

  const seenTools = new Set()
  for (const crop of farmCrops) {
    const tool = crop.harvestTool
    if (!tool?.itemId || seenTools.has(tool.itemId)) continue
    seenTools.add(tool.itemId)
    chips.push({
      kind: 'tool',
      id: tool.itemId,
      emoji: tool.emoji || '🛠',
      label: tool.name || 'Инструмент',
      value: Number(tool.count ?? countItem(items, tool.itemId)) || 0,
    })
  }
  if (!seenTools.size && axe?.count > 0) {
    chips.push({
      kind: 'tool',
      id: axe.itemId || ITEM_IDS.AXE,
      emoji: axe.emoji || '🪓',
      label: axe.name || 'Топор',
      value: Number(axe.count) || 0,
    })
  }

  return chips
}
