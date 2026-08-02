import { memo, useState } from 'react'
import VineFrame from './VineFrame'
import SoilField from './decor/SoilField'
import { PlotStatus, ITEM_IDS } from '../types/farm'
import '../styles/soilField.css'
import {
  getGrowthProgress,
  getGrowthStage,
  isDrySoon,
  isSoilMoist,
} from '../utils/farmTiming'
import { getEffectivePlotStatus, isPlotDry } from '../utils/plotActions'
import { createDexResolver } from '../utils/dexResolve'
import { listPlantableCrops } from '../utils/seedInventory'
import { cropDisplayLabel, findFarmCropByPlot } from '../utils/cropMatch'
import {
  harvestActionLabel,
  harvestBlockedLabel,
  resolveHarvestTool,
} from '../utils/harvestTool'
import { guideToItemPurchase } from '../utils/itemPurchaseGuide'
import GrowthProgressBar from './GrowthProgressBar'
import PlantSprite from './sprites/PlantSprite'
import WaterEffect from './WaterEffect'
import AutoWaterEffect from './AutoWaterEffect'

function formatCountdown(ms) {
  if (ms <= 0) return '0:00'
  const totalSec = Math.ceil(ms / 1000)
  const min = Math.floor(totalSec / 60)
  const sec = totalSec % 60
  return `${min}:${sec.toString().padStart(2, '0')}`
}


const STATUS_LABELS = {
  [PlotStatus.EMPTY]: 'Пустая грядка',
  [PlotStatus.GROWING]: 'Растёт',
  [PlotStatus.READY]: 'Готово!',
  [PlotStatus.WITHERED]: 'Засохло',
}

function resolvePlotCrop(plot, farmCrops, farmItemIds, itemCatalog) {
  return findFarmCropByPlot(farmCrops, plot, farmItemIds, itemCatalog)
}

function plotPropsEqual(prev, next) {
  const a = prev.plot
  const b = next.plot
  if (
    a.id !== b.id
    || a.status !== b.status
    || a.plantedAt !== b.plantedAt
    || a.ripeAt !== b.ripeAt
    || a.dryAt !== b.dryAt
    || a.cropId !== b.cropId
    || a.autowaterActive !== b.autowaterActive
  ) {
    return false
  }

  if (
    prev.waterAnimating !== next.waterAnimating
    || prev.waterAnimVariant !== next.waterAnimVariant
    || prev.isHighlighted !== next.isHighlighted
    || prev.isOnboardingSpotlight !== next.isOnboardingSpotlight
    || prev.needsWaterPulse !== next.needsWaterPulse
    || prev.isBusy !== next.isBusy
    || prev.tutorialDimmed !== next.tutorialDimmed
    || prev.grantPlantSeed !== next.grantPlantSeed
    || prev.grantWater !== next.grantWater
    || prev.waterCount !== next.waterCount
    || prev.autowaterCount !== next.autowaterCount
    || prev.items !== next.items
    || prev.axe !== next.axe
    || prev.farmItemIds !== next.farmItemIds
    || prev.farmCrops !== next.farmCrops
    || prev.seedCounts !== next.seedCounts
    || prev.balanceBar !== next.balanceBar
    || prev.itemCatalog !== next.itemCatalog
  ) {
    return false
  }

  const status = getEffectivePlotStatus(a, prev.now)
  if (status === PlotStatus.GROWING) {
    return Math.floor(prev.now / 1000) === Math.floor(next.now / 1000)
  }

  return true
}

function PlotCard({
  plot,
  now,
  onAction,
  waterAnimating = false,
  waterAnimVariant = 'water',
  isHighlighted = false,
  isOnboardingSpotlight = false,
  needsWaterPulse = false,
  isBusy = false,
  farmCrops = [],
  seedCounts = {},
  farmItemIds = null,
  axe = null,
  grantPlantSeed = false,
  grantWater = false,
  waterCount = 0,
  autowaterCount = 0,
  items = {},
  balanceBar = [],
  itemCatalog = null,
  tutorialDimmed = false,
}) {
  const [guideBusy, setGuideBusy] = useState(false)
  const dex = createDexResolver(itemCatalog, farmItemIds)

  const runPurchaseGuide = async (target) => {
    setGuideBusy(true)
    try {
      await guideToItemPurchase({ ...target, itemCatalog, farmItemIds })
    } finally {
      setGuideBusy(false)
    }
  }

  const actionBusy = isBusy || guideBusy
  const status = getEffectivePlotStatus(plot, now)
  const autowaterActive = Boolean(plot.autowaterActive)
  const needsWater = isPlotDry(plot, now)
  const isDry = status === PlotStatus.GROWING && needsWater
  const drySoon = status === PlotStatus.GROWING && !autowaterActive && isDrySoon(plot.dryAt, needsWater, now)
  const moist = status === PlotStatus.GROWING && (autowaterActive || isSoilMoist(plot.dryAt, needsWater, now))
  const plotCrop = resolvePlotCrop(plot, farmCrops, farmItemIds, itemCatalog)
  const cropLabel = cropDisplayLabel(plotCrop, plot, itemCatalog)

  const growthStage =
    status === PlotStatus.GROWING
      ? getGrowthStage(plot.plantedAt, plot.ripeAt, now)
      : null

  const growthProgress =
    status === PlotStatus.GROWING
      ? getGrowthProgress(plot.plantedAt, plot.ripeAt, now)
      : 0

  const countdown =
    status === PlotStatus.GROWING && plot.ripeAt
      ? formatCountdown(plot.ripeAt - now)
      : null

  const seedCtx = { seedCounts, items, farmItemIds, grantPlantSeed, balanceBar, itemCatalog }
  const plantableCrops = listPlantableCrops(farmCrops, seedCtx)
  const hasAnySeed = plantableCrops.length > 0
  const cropName = (crop) => crop.displayName || crop.seedName || (crop.key === 'tree' ? 'Дерево' : crop.key === 'tobacco' ? 'Табак' : 'Культура')
  const seedLabel = (crop) => crop.seedName || cropName(crop)
  const plantCols = Math.min(Math.max(plantableCrops.length, 1), 3)

  if (status === PlotStatus.EMPTY) {
    return (
      <div
        data-onboarding-plot={isOnboardingSpotlight ? String(plot.id) : undefined}
        className={`plot-empty-row ${tutorialDimmed ? 'onboarding-plot-dimmed' : ''} ${isOnboardingSpotlight ? 'onboarding-plot-highlight' : ''}`}
      >
        <div className="plot-empty-row-header">
          <span className="plot-empty-row-num">#{plot.id}</span>
          <span className="plot-empty-row-label">Пустая</span>
        </div>
        {hasAnySeed ? (
          <div className={`plot-empty-row-seeds cols-${plantCols}`}>
            {plantableCrops.map((crop) => (
              <button
                key={crop.key || crop.seedId}
                type="button"
                className="plot-empty-row-btn"
                disabled={actionBusy}
                title={cropName(crop)}
                aria-label={`Посадить: ${cropName(crop)}`}
                onClick={() => onAction(plot.id, 'plant', crop.seedId)}
              >
                <span className="plot-empty-row-btn-emoji" aria-hidden>{crop.seedEmoji}</span>
                {plantableCrops.length > 1 && (
                  <span className="plot-empty-row-btn-name">{cropName(crop)}</span>
                )}
              </button>
            ))}
          </div>
        ) : (
          <button
            type="button"
            className="plot-empty-row-shop"
            disabled={actionBusy}
            onClick={() => {
              const defaultCrop = farmCrops?.[0]
              const label = defaultCrop ? seedLabel(defaultCrop) : 'Саженец'
              runPurchaseGuide({
                itemId: defaultCrop?.seedId,
                name: label,
                emoji: defaultCrop?.seedEmoji ?? '🌱',
                search: defaultCrop?.seedId || label,
              })
            }}
          >
            Купить саженец
          </button>
        )}
      </div>
    )
  }

  const harvestTool = resolveHarvestTool(plotCrop, axe, items, farmItemIds, itemCatalog)
  const harvestBlockedByTool = status === PlotStatus.READY
    && harvestTool?.required
    && !harvestTool.owned
  const harvestLabel = harvestActionLabel(plotCrop, harvestTool)
  const harvestShopLabel = harvestBlockedLabel(harvestTool)

  const regularWaterId = plotCrop?.waterItemId ?? farmItemIds?.water ?? ITEM_IDS.WATER
  const regularWaterCost = plotCrop?.waterCostPerUse ?? 1
  const regularWaterEmoji = plotCrop?.waterEmoji ?? '💧'
  const regularWaterName = plotCrop?.waterName ?? 'Вода'
  const autowaterId = farmItemIds?.autowater ?? ITEM_IDS.AUTOWATER
  const regularWaterAvailable = grantWater
    || dex.countIn(items, regularWaterId) >= regularWaterCost
    || Number(waterCount ?? 0) >= regularWaterCost
  const autowaterAvailable = dex.countIn(items, autowaterId) >= 1
    || Number(autowaterCount ?? 0) >= 1
  const canInstallAutowater = status === PlotStatus.GROWING && !autowaterActive && autowaterAvailable
  const canWaterPlot = !autowaterActive && regularWaterAvailable
  const waterBlocked = status === PlotStatus.GROWING && isDry && !autowaterActive && !canWaterPlot

  return (
    <VineFrame
      data-onboarding-plot={isOnboardingSpotlight ? String(plot.id) : undefined}
      className={`transition-all duration-300 ${
        isOnboardingSpotlight
          ? 'onboarding-plot-highlight'
          : isHighlighted
            ? 'ring-2 ring-amber-300/70 scale-[1.02] z-10'
            : ''
      } ${needsWaterPulse ? 'plot-needs-water-pulse' : ''} ${
        tutorialDimmed ? 'onboarding-plot-dimmed' : ''
      }`}
    >
      <article className="relative flex flex-col">
      <div className="absolute top-2 left-2 z-10 px-2 py-0.5 rounded-lg bg-black/50 border border-amber-500/40 text-amber-100 text-xs font-bold">
        #{plot.id}
      </div>

      <div className="farm-soil-panel p-2 border-b border-amber-500/15">
        <div
          className={`farm-soil-inner relative h-36 flex items-end justify-center pb-2 transition-colors duration-500${
            autowaterActive ? ' farm-soil-autowater-active' : ''
          }`}
        >
          <SoilField
            status={status}
            moist={moist}
            dry={isDry}
            ready={status === PlotStatus.READY}
          />

          {waterAnimating && waterAnimVariant === 'autowater' && <AutoWaterEffect mode="burst" />}
          {waterAnimating && waterAnimVariant !== 'autowater' && <WaterEffect active />}
          {autowaterActive && !waterAnimating && <AutoWaterEffect mode="idle" />}

          {autowaterActive && (
            <div className="farm-autowater-badge" aria-label="Автополив активен">
              <span className="farm-autowater-badge-dot" aria-hidden />
              <span>Автополив</span>
            </div>
          )}

          <div className="relative z-10">
            <PlantSprite
              status={status}
              growthStage={growthStage}
              cropKey={plotCrop?.spriteKey ?? plotCrop?.key}
            />
          </div>
        </div>
      </div>

      <div className="p-3 space-y-2 farm-panel-body">
        <p className="text-center text-xs font-bold text-amber-100/90 uppercase tracking-widest plot-crop-label">
          {status === PlotStatus.GROWING || status === PlotStatus.READY
            ? cropLabel
            : STATUS_LABELS[status]}
        </p>

        {status === PlotStatus.GROWING && (
          <>
            <GrowthProgressBar progress={growthProgress} label={countdown ? `⏱ ${countdown}` : '⏱ …'} />

            {drySoon && !isDry && (
              <p className="text-center text-[10px] font-bold text-amber-300/90 bg-black/30 rounded-lg py-1 px-2 border border-amber-500/20 animate-pulse-soft">
                ⚠ Скоро засохнет. Полейте грядку
              </p>
            )}

            {isDry && (
              <p className="text-center text-xs text-orange-300 font-semibold animate-pulse plot-water-hint">
                💧 Необходимо полить!
              </p>
            )}
          </>
        )}

        <div className="flex flex-col gap-1.5">
          {status === PlotStatus.GROWING && canInstallAutowater && (
            <button
              type="button"
              className="farm-btn-autowater w-full"
              disabled={actionBusy}
              onClick={() => onAction(plot.id, 'autowater')}
            >
              Автополив
              <span className="ml-1" aria-hidden>🚰</span>
              <span className="farm-btn-autowater-note">до урожая без ручного полива</span>
            </button>
          )}

          {status === PlotStatus.GROWING && autowaterActive && (
            <p className="text-center text-[10px] font-semibold text-sky-200/80">
              🚰 Автополив активен - поливать вручную не нужно
            </p>
          )}

          {status === PlotStatus.GROWING && isDry && !autowaterActive && (
            <>
              {regularWaterAvailable && (
                <button
                  type="button"
                  className="farm-btn-water w-full"
                  disabled={actionBusy}
                  onClick={() => onAction(plot.id, 'water', { waterItemId: regularWaterId })}
                >
                  Полить
                  <span className="ml-1" aria-hidden>{regularWaterEmoji}</span>
                  <span className="block text-[10px] font-normal opacity-90">
                    {regularWaterCost} {regularWaterName.toLowerCase()}
                  </span>
                </button>
              )}
              {waterBlocked && (
                <button
                  type="button"
                  className="text-center text-[10px] font-bold text-amber-200/90 bg-black/25 rounded-lg py-1 px-2 border border-amber-400/40 w-full active:opacity-70 transition-opacity cursor-pointer"
                  disabled={actionBusy}
                  onClick={() => {
                    runPurchaseGuide({
                      itemId: regularWaterId,
                      name: regularWaterName,
                      emoji: regularWaterEmoji,
                    })
                  }}
                >
                  🛒 Нет воды - купить
                </button>
              )}
            </>
          )}

          {status === PlotStatus.READY && (
            <>
              <button
                type="button"
                className="farm-btn-harvest w-full"
                disabled={actionBusy}
                onClick={() => {
                  if (harvestBlockedByTool) {
                    runPurchaseGuide({
                      itemId: harvestTool?.itemId,
                      name: harvestTool?.name,
                      emoji: harvestTool?.emoji,
                    })
                  } else {
                    onAction(plot.id, 'harvest')
                  }
                }}
              >
                {harvestBlockedByTool ? harvestShopLabel : harvestLabel}
              </button>
              {harvestTool?.owned && (
                <p className="text-center text-[10px] text-amber-200/70">
                  {harvestTool.emoji} −{harvestTool.costPerHarvest} · осталось {harvestTool.count}
                </p>
              )}
              {plotCrop?.seedDropPercent > 0 ? (
                <p className="text-center text-[10px] font-semibold text-emerald-200/85">
                  Шанс {plotCrop.seedDropPercent}%: {plotCrop.seedEmoji ?? '🌱'} {cropName(plotCrop)}
                </p>
              ) : null}
            </>
          )}

          {status === PlotStatus.WITHERED && (
            <button
              type="button"
              className="farm-btn-danger w-full"
              disabled={actionBusy}
              onClick={() => onAction(plot.id, 'clear')}
            >
              Очистить грядку
              <span className="block text-[10px] font-normal opacity-90">10 КУТ</span>
            </button>
          )}
        </div>
      </div>
      </article>
    </VineFrame>
  )
}

export default memo(PlotCard, plotPropsEqual)
