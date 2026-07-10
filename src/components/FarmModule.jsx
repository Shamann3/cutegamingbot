import { useEffect, useRef, useState } from 'react'
import { ITEM_IDS } from '../types/farm'
import { getPerfClockMs } from '../utils/devicePerf'
import { useSettings } from '../context/SettingsContext'
import { useOnboardingOptional } from '../context/OnboardingContext'
import { useFarm } from '../hooks/useFarm'
import { useEquippedCosmetics } from '../hooks/useEquippedCosmetics'
import { useShopLayout } from '../hooks/useShopLayout'
import { farmGridClassForColumns } from '../utils/shopLayout'
import { canPerformAction, getEffectivePlotStatus, isPlotDry } from '../utils/plotActions'
import { buildFarmSlots } from '../utils/farmSlots'
import { WATER_ANIM_MS } from '../utils/farmTiming'
import FarmBackground from './FarmBackground'
import FarmPet from './FarmPet'
import FarmHeader from './FarmHeader'
import FarmToastLayer from './FarmToastLayer'
import PlotCard from './PlotCard'
import BuyPlotCard from './BuyPlotCard'
import BalanceBar from './BalanceBar'
import DonateModal from './DonateModal'
import TabAtmosphere from './TabAtmosphere'
import { useContextualDonate } from '../hooks/useContextualDonate'
import '../styles/cosmetic-effects.css'

export default function FarmModule({ isActive = true }) {
  const { playSound, performanceMode, turboMode } = useSettings()
  const onboarding = useOnboardingOptional()
  const { equipped } = useEquippedCosmetics()
  const highlightPlotId = onboarding?.highlightPlotId ?? null
  const clockMs = getPerfClockMs(performanceMode)
  const { columns } = useShopLayout()
  const plotsGridClass = farmGridClassForColumns(columns)
  const {
    plots,
    farmItemIds,
    seedCounts,
    farmCrops,
    balanceBar,
    itemCatalog,
    items,
    axe,
    waterCount,
    autowaterCount,
    kut,
    ownedPlots,
    maxPlots,
    nextPlotPrice,
    loading,
    error,
    errorCode,
    actionMessage,
    gainToasts,
    spendToasts,
    actions,
    isPreview,
  } = useFarm({ isActive })

  const [now, setNow] = useState(() => Date.now())
  const [waterAnimPlots, setWaterAnimPlots] = useState(() => new Map())
  const [busyPlotId, setBusyPlotId] = useState(null)
  const [buyingPlot, setBuyingPlot] = useState(false)
  const actionLockRef = useRef(new Set())
  const waterTimeoutsRef = useRef(new Map())
  const {
    donateOpen,
    donateContext,
    openContextualDonate,
    closeDonate,
  } = useContextualDonate()

  const slots = buildFarmSlots({
    plots,
    ownedPlots,
    maxPlots,
    nextPlotPrice,
  })

  useEffect(() => {
    if (!isActive) return undefined

    const tick = () => setNow(Date.now())
    tick()

    const id = setInterval(tick, clockMs)

    const onVisibility = () => {
      if (document.visibilityState === 'visible') tick()
    }
    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      clearInterval(id)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [clockMs, isActive])

  useEffect(() => {
    const timeouts = waterTimeoutsRef.current
    return () => {
      timeouts.forEach((t) => clearTimeout(t))
      timeouts.clear()
    }
  }, [])

  const triggerWaterAnim = (plotId, variant = 'water') => {
    setWaterAnimPlots((prev) => new Map(prev).set(plotId, variant))
    const existing = waterTimeoutsRef.current.get(plotId)
    if (existing) clearTimeout(existing)
    const timeoutId = setTimeout(() => {
      setWaterAnimPlots((prev) => {
        const next = new Map(prev)
        next.delete(plotId)
        return next
      })
      waterTimeoutsRef.current.delete(plotId)
    }, WATER_ANIM_MS)
    waterTimeoutsRef.current.set(plotId, timeoutId)
  }

  const handlePlotAction = async (plotId, action, extra) => {
    if (actionLockRef.current.has(plotId)) return

    if (onboarding?.tutorialPlotOnly && plotId !== onboarding.tutorialPlotId) return

    const plot = plots.find((p) => p.id === plotId)
    if (!plot || !canPerformAction(plot, action, Date.now())) return

    actionLockRef.current.add(plotId)
    setBusyPlotId(plotId)

    try {
      if (action === 'plant') playSound('plant')
      if (action === 'water') {
        playSound('water')
        if (!turboMode) triggerWaterAnim(plotId, 'water')
      }
      if (action === 'autowater') {
        playSound('plant')
        if (!turboMode) triggerWaterAnim(plotId, 'autowater')
      }
      if (action === 'harvest') playSound('harvest')
      if (action === 'clear') playSound('clear')

      if (action === 'plant') {
        const resolvedSeedId =
          extra ?? farmItemIds?.seed ?? ITEM_IDS.SEED
        await actions.plant(plotId, resolvedSeedId)
      } else if (action === 'water') {
        await actions.water(plotId, extra?.waterItemId)
      } else if (action === 'autowater') {
        await actions.autowater(plotId)
      } else {
        await actions[action](plotId)
      }
      onboarding?.notifyFarmAction?.(action, plotId)
    } catch {
      // ошибка показывается в баннере через хук
    } finally {
      // Release the lock once the API responds (not after a fixed timer),
      // preventing a 400ms window where double-tapping fires a second request.
      actionLockRef.current.delete(plotId)
      setBusyPlotId((current) => (current === plotId ? null : current))
    }
  }

  const [batchBusy, setBatchBusy] = useState(false)

  // Грядки готовые к сбору
  const readyPlots = plots.filter(
    (p) => getEffectivePlotStatus(p, now) === 'READY'
  )

  // Грядки которые нужно полить (и есть вода)
  const dryPlots = plots.filter(
    (p) => getEffectivePlotStatus(p, now) === 'GROWING' && isPlotDry(p, now)
  )
  const hasWater = waterCount > 0 || onboarding?.grantWater

  const handleHarvestAll = async () => {
    if (batchBusy || readyPlots.length === 0) return
    setBatchBusy(true)
    playSound('harvest')
    try {
      for (const plot of readyPlots) {
        if (actionLockRef.current.has(plot.id)) continue
        actionLockRef.current.add(plot.id)
        try {
          await actions.harvest(plot.id)
          onboarding?.notifyFarmAction?.('harvest', plot.id)
        } catch { /* продолжаем */ } finally {
          actionLockRef.current.delete(plot.id)
        }
      }
    } finally {
      setBatchBusy(false)
    }
  }

  const handleWaterAll = async () => {
    if (batchBusy || dryPlots.length === 0 || !hasWater) return
    setBatchBusy(true)
    playSound('water')
    try {
      for (const plot of dryPlots) {
        if (actionLockRef.current.has(plot.id)) continue
        actionLockRef.current.add(plot.id)
        try {
          if (!turboMode) triggerWaterAnim(plot.id, 'water')
          await actions.water(plot.id)
          onboarding?.notifyFarmAction?.('water', plot.id)
        } catch { /* продолжаем */ } finally {
          actionLockRef.current.delete(plot.id)
        }
      }
    } finally {
      setBatchBusy(false)
    }
  }

  const handleBuyPlot = async () => {
    if (buyingPlot) return
    setBuyingPlot(true)
    try {
      playSound('plant')
      await actions.buyPlot()
    } catch {
      // error banner
    } finally {
      setBuyingPlot(false)
    }
  }

  return (
    <div className="relative min-h-screen tab-theme-farm farm-module">
      <FarmBackground />
      <TabAtmosphere variant="farm" />
      <FarmToastLayer gainToasts={gainToasts} spendToasts={spendToasts} />

      {/* Закреплённая панель ресурсов над табами */}
      {isActive && (
        <BalanceBar
          fixed
          balanceBar={balanceBar}
          kut={kut}
          farmCrops={farmCrops}
          seedCounts={seedCounts}
          items={items}
          waterCount={waterCount}
          axe={axe}
          anyPlotDry={plots.some((p) => isPlotDry(p, now))}
        />
      )}

      <div className="relative z-10 farm-shell py-3 farm-shell-with-bar animate-slide-up">
        <FarmHeader isPreview={isPreview} />

        {loading && plots.length === 0 ? (
          <div className="text-center py-12 text-amber-100 font-semibold drop-shadow-md">
            Загрузка фермы…
          </div>
        ) : (
          <>
            {error && !onboarding?.visible && (
              <div className={`mb-4 rounded-xl px-4 py-3 text-sm font-semibold farm-error-banner farm-error-${errorCode || 'api'}`}>
                {error}
              </div>
            )}

            {actionMessage && !onboarding?.visible ? (
              <div className="farm-action-toast mb-4" role="status">
                {actionMessage}
              </div>
            ) : null}

            {/* Кнопки массовых действий */}
            {!onboarding?.visible && (readyPlots.length >= 4 || (dryPlots.length >= 4 && hasWater)) && (
              <div className="farm-batch-bar">
                {readyPlots.length >= 4 && (
                  <button
                    type="button"
                    className="farm-batch-btn farm-batch-btn--harvest"
                    disabled={batchBusy}
                    onClick={handleHarvestAll}
                  >
                    <span className="farm-batch-icon">🧺</span>
                    <span className="farm-batch-label">
                      Собрать все
                      <span className="farm-batch-count">{readyPlots.length}</span>
                    </span>
                  </button>
                )}
                {dryPlots.length >= 4 && hasWater && (
                  <button
                    type="button"
                    className="farm-batch-btn farm-batch-btn--water"
                    disabled={batchBusy}
                    onClick={handleWaterAll}
                  >
                    <span className="farm-batch-icon">💧</span>
                    <span className="farm-batch-label">
                      Полить все
                      <span className="farm-batch-count">{dryPlots.length}</span>
                    </span>
                  </button>
                )}
              </div>
            )}

            <section aria-label="Грядки" className="mb-6 relative">
              {equipped.pet && <FarmPet emoji={equipped.pet.emoji} />}
              <div className={`farm-plots-grid ${plotsGridClass} ${equipped.plot ? `plot-skin--${equipped.plot.code}` : ''}`}>
                {slots.map((slot) => {
                  if (slot.type === 'plot') {
                    return (
                      <PlotCard
                        key={`plot-${slot.plot.id}`}
                        plot={slot.plot}
                        now={now}
                        onAction={handlePlotAction}
                        waterAnimating={waterAnimPlots.has(slot.plot.id)}
                        waterAnimVariant={waterAnimPlots.get(slot.plot.id) ?? 'water'}
                        isHighlighted={highlightPlotId === slot.plot.id}
                        isOnboardingSpotlight={highlightPlotId === slot.plot.id}
                        needsWaterPulse={isPlotDry(slot.plot, now)}
                        isBusy={busyPlotId === slot.plot.id}
                        farmCrops={farmCrops}
                        seedCounts={seedCounts}
                        balanceBar={balanceBar}
                        farmItemIds={farmItemIds}
                        itemCatalog={itemCatalog}
                        items={items}
                        axe={axe}
                        grantPlantSeed={onboarding?.grantPlantSeed}
                        grantWater={onboarding?.grantWater}
                        waterCount={waterCount}
                        autowaterCount={autowaterCount}
                        tutorialDimmed={
                          onboarding?.tutorialPlotOnly && slot.plot.id !== onboarding.tutorialPlotId
                        }
                      />
                    )
                  }
                  if (slot.type === 'buy') {
                    return (
                      <BuyPlotCard
                        key="buy-next-plot"
                        price={slot.price}
                        kut={kut}
                        isBusy={buyingPlot}
                        onBuy={handleBuyPlot}
                        onContextualDonate={openContextualDonate}
                      />
                    )
                  }
                  return null
                })}
              </div>
            </section>
          </>
        )}
      </div>

      <DonateModal
        isOpen={donateOpen}
        onClose={closeDonate}
        context={donateContext}
      />
    </div>
  )
}
