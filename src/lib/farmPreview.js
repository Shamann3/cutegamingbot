/**
 * Локальный превью UI без сервера (VITE_FARM_PREVIEW=true).
 */

import { PlotStatus, ITEM_IDS, MAX_PLOTS } from '../types/farm'
import { plotBuyPrice } from '../types/farm'
import { buildBalanceBarChips } from '../utils/balanceBar'
import {
  growTimeMsForCrop,
  WATER_INTERVAL_MS,
  WILT_GRACE_MS,
} from '../utils/farmTiming'

const PREVIEW_FARM_CROPS = [
  {
    key: 'tree',
    displayName: 'Дерево',
    seedId: ITEM_IDS.SEED,
    seedName: 'Саженец дерева',
    seedEmoji: '🌱',
    harvestId: ITEM_IDS.TREE,
    harvestName: 'Дерево',
    harvestEmoji: '🪵',
    requiresAxe: true,
    growSeconds: 20 * 60,
    waterItemId: ITEM_IDS.WATER,
    waterName: 'Вода',
    waterEmoji: '💧',
    harvestTool: {
      itemId: ITEM_IDS.AXE,
      name: 'Топор',
      emoji: '🪓',
      count: 1,
      costPerHarvest: 1,
    },
  },
  {
    key: 'tobacco',
    displayName: 'Табак',
    seedId: ITEM_IDS.TOBACCO_SEED,
    seedName: 'Сажанец табака',
    seedEmoji: '🍃',
    harvestId: ITEM_IDS.TOBACCO,
    harvestName: 'Табак',
    harvestEmoji: '🍂',
    requiresAxe: true,
    growSeconds: 10 * 60,
    waterItemId: ITEM_IDS.WATER,
    waterName: 'Вода',
    waterEmoji: '💧',
    harvestTool: {
      itemId: ITEM_IDS.AXE,
      name: 'Топор',
      emoji: '🪓',
      count: 1,
      costPerHarvest: 1,
    },
  },
]

function initialState() {
  return {
    kut: 250,
    items: {
      [ITEM_IDS.SEED]: 2,
      [ITEM_IDS.TOBACCO_SEED]: 1,
      [ITEM_IDS.TREE]: 3,
      [ITEM_IDS.AXE]: 1,
      [ITEM_IDS.WATER]: 3,
      [ITEM_IDS.AUTOWATER]: 2,
    },
    toolDurability: { [ITEM_IDS.AXE]: 100 },
    ownedPlots: 1,
    maxPlots: MAX_PLOTS,
    plots: [{ id: 1, status: PlotStatus.EMPTY }],
  }
}

let state = initialState()

function seedCount(items) {
  return Number(items[ITEM_IDS.SEED] ?? items.sajeneztree ?? 0)
}

function tobaccoSeedCount(items) {
  return Number(items[ITEM_IDS.TOBACCO_SEED] ?? 0)
}

function tobaccoCount(items) {
  return Number(items[ITEM_IDS.TOBACCO] ?? 0)
}

function axeCount(items) {
  return Number(items[ITEM_IDS.AXE] ?? 0)
}

function autowaterCount(items) {
  return Number(items[ITEM_IDS.AUTOWATER] ?? 0)
}

function waterCount(items) {
  return Number(items[ITEM_IDS.WATER] ?? 0)
}

function plantableSeedCounts(items) {
  const counts = {}
  for (const crop of PREVIEW_FARM_CROPS) {
    const n = Number(items[crop.seedId] ?? 0)
    counts[crop.seedId] = n
  }
  return counts
}

function treeCount(items) {
  return Number(items[ITEM_IDS.TREE] ?? items.justtree ?? 0)
}

function previewAxeState() {
  const count = axeCount(state.items)
  return {
    itemId: ITEM_IDS.AXE,
    name: 'Топор',
    emoji: '🪓',
    owned: count >= 1,
    count,
    costPerHarvest: 1,
  }
}

function syncGrowingPlots() {
  const now = Date.now()

  for (const plot of state.plots) {
    if (plot.status !== PlotStatus.GROWING) continue
    if (plot.autowaterActive) {
      if (plot.ripeAt && now >= plot.ripeAt) {
        plot.status = PlotStatus.READY
        plot.needsWater = false
        delete plot.wiltAt
      }
      continue
    }

    if (plot.ripeAt && now >= plot.ripeAt) {
      plot.status = PlotStatus.READY
      plot.needsWater = false
      delete plot.wiltAt
      continue
    }

    if (plot.wiltAt && now >= plot.wiltAt) {
      plot.status = PlotStatus.WITHERED
      continue
    }

    if (plot.dryAt && now >= plot.dryAt && !plot.needsWater) {
      plot.needsWater = true
      plot.wiltAt = now + WILT_GRACE_MS
    }
  }
}

function buildMeta() {
  syncGrowingPlots()

  const nextId = state.ownedPlots < state.maxPlots ? state.ownedPlots + 1 : null
  const seed_counts = plantableSeedCounts(state.items)
  const axe = previewAxeState()
  axe.count = axeCount(state.items)
  const farm_crops = PREVIEW_FARM_CROPS.map((crop) => ({
    ...crop,
    harvestTool: {
      ...crop.harvestTool,
      count: axeCount(state.items),
    },
  }))
  return {
    ownedPlots: state.ownedPlots,
    maxPlots: state.maxPlots,
    nextPlotId: nextId,
    nextPlotPrice: nextId ? plotBuyPrice(nextId) : null,
    seedCount: seedCount(state.items),
    tobaccoSeedCount: tobaccoSeedCount(state.items),
    seedCounts: seed_counts,
    farmItemIds: ITEM_IDS,
    farmCrops: farm_crops,
    balanceBar: buildBalanceBarChips({
      kut: state.kut,
      farmCrops: farm_crops,
      seedCounts: seed_counts,
      items: state.items,
      waterCount: waterCount(state.items),
      axe,
    }),
    axe,
    waterCount: waterCount(state.items),
    autowaterCount: autowaterCount(state.items),
    items: { ...state.items },
    inventory: { justtree: treeCount(state.items) },
    kut: state.kut,
    plots: state.plots.map((p) => ({ ...p })),
    onboarding: {
      done: !previewOnboardingActive,
      active: previewOnboardingActive,
    },
  }
}

function notifyRow(itemId, amount, name, emoji) {
  return { itemId: String(itemId), amount, name, emoji }
}

export function previewFetchState(extra = {}) {
  return Promise.resolve({ ...buildMeta(), ...extra })
}

export function previewBuyPlot() {
  const nextId = state.ownedPlots + 1
  const price = plotBuyPrice(nextId)
  if (state.kut < price) throw new Error(`У Вас недостаточно кут (нужно ${price})`)
  state.kut -= price
  state.ownedPlots = nextId
  state.plots.push({ id: nextId, status: PlotStatus.EMPTY })
  return previewFetchState()
}

export function previewPlant(plotId, seedItemId = ITEM_IDS.SEED) {
  const crop = PREVIEW_FARM_CROPS.find((entry) => entry.seedId === seedItemId)
  if (!crop) throw new Error('Неизвестный саженец')

  const available =
    seedItemId === ITEM_IDS.SEED
      ? seedCount(state.items)
      : tobaccoSeedCount(state.items)
  if (available < 1) {
    throw new Error('У Вас нет саженца. Купите в магазине')
  }

  const plot = state.plots.find((p) => p.id === plotId)
  if (!plot || plot.status !== PlotStatus.EMPTY) throw new Error('Грядка уже занята')

  state.items[seedItemId] = available - 1
  if (state.items[seedItemId] <= 0) delete state.items[seedItemId]
  if (seedItemId === ITEM_IDS.SEED) delete state.items.sajeneztree

  const growMs = growTimeMsForCrop(seedItemId, PREVIEW_FARM_CROPS)
  const now = Date.now()
  plot.status = PlotStatus.GROWING
  plot.cropId = seedItemId
  plot.plantedAt = now
  plot.ripeAt = now + growMs
  plot.dryAt = now + WATER_INTERVAL_MS
  plot.needsWater = false
  plot.wiltAt = null
  plot.autowaterActive = false
  return previewFetchState({
    farmSpent: [notifyRow(seedItemId, 1, crop.seedName, crop.seedEmoji)],
  })
}

export function previewInstallAutowater(plotId) {
  const plot = state.plots.find((p) => p.id === plotId)
  if (!plot || plot.status !== PlotStatus.GROWING) throw new Error('На грядке ничего не растёт')
  if (plot.autowaterActive) throw new Error('Автополив уже установлен на этой грядке')
  if (autowaterCount(state.items) < 1) throw new Error('У Вас нет автополива. Скрафтите в разделе «Крафты»')

  const autowaterId = ITEM_IDS.AUTOWATER
  state.items[autowaterId] = autowaterCount(state.items) - 1
  if (state.items[autowaterId] <= 0) delete state.items[autowaterId]

  plot.autowaterActive = true
  plot.needsWater = false
  plot.wiltAt = null
  plot.dryAt = null
  return previewFetchState({
    farmSpent: [notifyRow(ITEM_IDS.AUTOWATER, 1, 'Автополив', '🚰')],
  })
}

export function previewWater(plotId, waterItemId = null) {
  const plot = state.plots.find((p) => p.id === plotId)
  if (!plot || plot.status !== PlotStatus.GROWING) throw new Error('На грядке ничего не растёт')
  if (plot.autowaterActive) throw new Error('Автополив уже поливает грядку')

  if (waterItemId && waterItemId !== ITEM_IDS.WATER) {
    throw new Error('Этим предметом нельзя полить грядку')
  }

  if (waterCount(state.items) < 1) throw new Error('У Вас нет воды. Купите в магазине')
    state.items[ITEM_IDS.WATER] = waterCount(state.items) - 1
    if (state.items[ITEM_IDS.WATER] <= 0) delete state.items[ITEM_IDS.WATER]

  plot.needsWater = false
  plot.wiltAt = null
  const ripeAt = plot.ripeAt ?? Date.now()
  const nextDry = Date.now() + WATER_INTERVAL_MS
  plot.dryAt = nextDry < ripeAt ? nextDry : null
  return previewFetchState({
    farmSpent: [notifyRow(ITEM_IDS.WATER, 1, 'Вода', '💧')],
  })
}

export function previewHarvest(plotId) {
  const plot = state.plots.find((p) => p.id === plotId)
  if (!plot) throw new Error('Нет грядки')
  if (plot.status !== PlotStatus.READY) throw new Error('Урожай ещё не готов')

  const crop =
    PREVIEW_FARM_CROPS.find((entry) => entry.seedId === plot.cropId) ??
    PREVIEW_FARM_CROPS[0]

  if (crop.requiresAxe) {
    if (axeCount(state.items) < 1) throw new Error('Нужен топор для сбора урожая')
    const next = axeCount(state.items) - 1
    if (next <= 0) {
      delete state.items[ITEM_IDS.AXE]
      delete state.toolDurability[ITEM_IDS.AXE]
    } else {
      state.items[ITEM_IDS.AXE] = next
    }
  }

  plot.status = PlotStatus.EMPTY
  delete plot.cropId
  delete plot.plantedAt
  delete plot.ripeAt
  delete plot.dryAt
  delete plot.needsWater
  delete plot.wiltAt
  delete plot.autowaterActive

  const gained = 1
  const harvestId = crop.key === 'tobacco' ? ITEM_IDS.TOBACCO : ITEM_IDS.TREE
  if (crop.key === 'tobacco') {
    state.items[ITEM_IDS.TOBACCO] = tobaccoCount(state.items) + gained
  } else {
    state.items[ITEM_IDS.TREE] = treeCount(state.items) + gained
    delete state.items.justtree
    previewOnboardingTrackHarvest(gained)
  }
  return previewFetchState({
    farmGained: [notifyRow(harvestId, gained, crop.harvestName, crop.harvestEmoji)],
    farmSpent: crop.requiresAxe
      ? [notifyRow(ITEM_IDS.AXE, 1, 'Топор', '🪓')]
      : [],
  })
}

export function previewClear(plotId) {
  const plot = state.plots.find((p) => p.id === plotId)
  if (!plot || plot.status !== PlotStatus.WITHERED) throw new Error('Растение на грядке ещё не засохло')
  if (state.kut < 10) throw new Error('У Вас недостаточно кут')
  state.kut -= 10
  plot.status = PlotStatus.EMPTY
  delete plot.plantedAt
  delete plot.ripeAt
  delete plot.dryAt
  delete plot.needsWater
  delete plot.wiltAt
  return previewFetchState()
}

let previewOnboardingActive = false
let previewSeedGranted = 0
let previewDemoLogs = 0
let previewOnboardingStep = 0

function previewOnboardingMeta() {
  return {
    onboarding: {
      done: !previewOnboardingActive && previewSeedGranted === 0 && previewDemoLogs === 0,
      active: previewOnboardingActive,
      step: previewOnboardingStep,
    },
  }
}

function previewStateWithOnboarding() {
  return Promise.resolve({ ...buildMeta(), ...previewOnboardingMeta() })
}

export function previewOnboardingStart() {
  previewOnboardingActive = true
  const plot = state.plots.find((p) => p.id === 1)
  if (plot?.status === PlotStatus.WITHERED) {
    plot.status = PlotStatus.EMPTY
    delete plot.plantedAt
    delete plot.ripeAt
    delete plot.dryAt
    delete plot.needsWater
    delete plot.wiltAt
  }
  if (seedCount(state.items) < 1 && plot?.status === PlotStatus.EMPTY) {
    state.items[ITEM_IDS.SEED] = (state.items[ITEM_IDS.SEED] ?? 0) + 1
    previewSeedGranted = 1
  }
  return previewStateWithOnboarding()
}

export function previewOnboardingPreparePlant() {
  previewOnboardingStep = 2
  const plot = state.plots.find((p) => p.id === 1)
  if (plot) {
    plot.status = PlotStatus.EMPTY
    delete plot.plantedAt
    delete plot.ripeAt
    delete plot.dryAt
    delete plot.needsWater
    delete plot.wiltAt
  }
  if (seedCount(state.items) < 1) {
    state.items[ITEM_IDS.SEED] = (state.items[ITEM_IDS.SEED] ?? 0) + 1
    previewSeedGranted = 1
  }
  return previewStateWithOnboarding()
}

export function previewOnboardingPrepareWater() {
  previewOnboardingStep = 3
  const plot = state.plots.find((p) => p.id === 1)
  if (!plot || plot.status !== PlotStatus.GROWING) return previewStateWithOnboarding()
  const now = Date.now()
  plot.needsWater = true
  plot.dryAt = now - 1000
  plot.wiltAt = now + WILT_GRACE_MS
  if (waterCount(state.items) < 1) {
    state.items[ITEM_IDS.WATER] = 1
  }
  return previewStateWithOnboarding()
}

export function previewOnboardingPrepareHarvest() {
  previewOnboardingStep = 4
  const plot = state.plots.find((p) => p.id === 1)
  if (!plot) return previewStateWithOnboarding()
  plot.status = PlotStatus.READY
  plot.needsWater = false
  delete plot.wiltAt
  delete plot.dryAt
  return previewStateWithOnboarding()
}

export function previewOnboardingSaveStep(step) {
  previewOnboardingStep = Math.max(0, Math.min(Number(step) || 0, 7))
  return previewStateWithOnboarding()
}

export function previewOnboardingComplete() {
  if (previewDemoLogs > 0) {
    const current = treeCount(state.items)
    const next = Math.max(0, current - previewDemoLogs)
    if (next > 0) state.items[ITEM_IDS.TREE] = next
    else delete state.items[ITEM_IDS.TREE]
    delete state.items.justtree
    previewDemoLogs = 0
  }
  const plot = state.plots.find((p) => p.id === 1)
  if (previewSeedGranted > 0 && plot?.status === PlotStatus.EMPTY) {
    const seeds = seedCount(state.items)
    if (seeds > 0) {
      state.items[ITEM_IDS.SEED] = seeds - 1
      if (state.items[ITEM_IDS.SEED] <= 0) delete state.items[ITEM_IDS.SEED]
    }
    previewSeedGranted = 0
  }
  previewOnboardingActive = false
  previewOnboardingStep = 0
  return previewStateWithOnboarding()
}

export function previewOnboardingTrackHarvest(amount = 2) {
  if (previewOnboardingActive) previewDemoLogs += amount
}
