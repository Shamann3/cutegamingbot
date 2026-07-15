import { createDexResolver } from './dexResolve'
import { looksLikeRawItemId } from './cropMatch'

function humanizeToolName(name, cropKey, itemCatalog, itemRef) {
  if (name && !looksLikeRawItemId(name)) return name
  if (itemCatalog && itemRef) {
    const dex = createDexResolver(itemCatalog)
    const fromDex = dex.catalogName(itemRef, '')
    if (fromDex && !looksLikeRawItemId(fromDex)) return fromDex
  }
  if (cropKey === 'tree' || cropKey === 'tobacco') return 'Топор'
  return 'Инструмент'
}

function cropNeedsHarvestTool(crop) {
  if (!crop) return false
  return Boolean(
    crop.requiresHarvestTool
    || crop.requiresAxe
    || crop.harvestTool?.required,
  )
}

/** Инструмент для сбора урожая через dex (id / name / emoji). */
export function resolveHarvestTool(
  plotCrop,
  axe,
  items = {},
  farmItemIds = null,
  itemCatalog = null,
) {
  if (!cropNeedsHarvestTool(plotCrop)) return null

  const dex = createDexResolver(itemCatalog, farmItemIds)
  const cost = plotCrop?.harvestTool?.costPerHarvest ?? axe?.costPerHarvest ?? 1
  const toolRef = plotCrop?.harvestTool?.itemId ?? farmItemIds?.axe ?? axe?.itemId

  let count = Math.max(
    Number(plotCrop?.harvestTool?.count ?? 0),
    Number(axe?.count ?? 0),
    dex.countIn(items, toolRef),
  )

  const emoji = plotCrop?.harvestTool?.emoji
    ?? axe?.emoji
    ?? dex.catalogEmoji(toolRef, '🪓')
  const name = humanizeToolName(
    plotCrop?.harvestTool?.name ?? axe?.name,
    plotCrop?.key,
    itemCatalog,
    toolRef,
  )

  return {
    itemId: dex.resolve(toolRef),
    name,
    emoji,
    required: true,
    costPerHarvest: cost,
    count,
    owned: count >= cost,
  }
}

export function harvestActionLabel(plotCrop, harvestTool) {
  const emoji = harvestTool?.emoji ?? '🪓'
  if (plotCrop?.key === 'tree') {
    return `Срубить ${emoji}`
  }
  const harvestEmoji = plotCrop?.harvestEmoji ?? '📦'
  return `Собрать ${harvestEmoji}`
}

export function harvestBlockedLabel(harvestTool) {
  const emoji = harvestTool?.emoji ?? '🪓'
  const name = harvestTool?.name ?? 'Топор'
  return `Купить ${emoji} ${name}`
}
