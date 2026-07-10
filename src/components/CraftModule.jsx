import { useEffect, useMemo, useRef, useState } from 'react'
import VineFrame from './VineFrame'
import CraftRitualEffect from './CraftRitualEffect'
import { useSettings } from '../context/SettingsContext'
import FarmBackground from './FarmBackground'
import KutBalance from './KutBalance'
import TabAtmosphere from './TabAtmosphere'
import { useCraft } from '../hooks/useCraft'
import {
  buildCraftInventory,
  findMatchingRecipe,
  formatRecipeLine,
  ingredientPairKey,
} from '../utils/craftMatch'
import { playCraftRitualSound } from '../utils/sounds'
import { acquireScrollLock, releaseScrollLock } from '../utils/scrollLock'
import { fuseDurationMs } from '../utils/craftRitualOrbit'

const RITUAL_INVOKE_MS = { full: 480, lite: 260, turbo: 0 }
const RITUAL_SIGIL_MS = { full: 1800, lite: 750, turbo: 0 }
const RITUAL_BLEND_MS = { full: 0, lite: 0, turbo: 380 }
const RITUAL_REVEAL_MS = { full: 1300, lite: 600, turbo: 240 }
const RITUAL_OVERLAP_MS = { full: 520, lite: 280, turbo: 0 }
const RITUAL_ALIGNMENTS = { full: 2, lite: 2 }
const RITUAL_ORBIT_MIN_MS = { full: 2000, lite: 1000 }

function errorClass(code) {
  if (code === 'auth') return 'craft-toast-auth'
  if (code === 'rate_limit') return 'craft-toast-rate'
  if (code === 'maintenance') return 'craft-toast-maint'
  return 'craft-toast-error'
}

function craftHint(slotA, slotB, matchedRecipe, ritualPhase) {
  if (ritualPhase) return ''
  if (!slotA || !slotB) return 'Два слота'
  if (!matchedRecipe) return 'Нет рецепта'
  return `${matchedRecipe.result.emoji} ${matchedRecipe.result.name}`
}

function ritualTiming(turboMode, liteMode) {
  const tier = turboMode ? 'turbo' : liteMode ? 'lite' : 'full'
  return {
    invoke: RITUAL_INVOKE_MS[tier],
    sigil: RITUAL_SIGIL_MS[tier],
    blend: RITUAL_BLEND_MS[tier],
    reveal: RITUAL_REVEAL_MS[tier],
    overlap: RITUAL_OVERLAP_MS[tier],
    alignments: RITUAL_ALIGNMENTS[tier],
    orbitMinMs: RITUAL_ORBIT_MIN_MS[tier],
    tier,
  }
}

function waitFrame() {
  return new Promise((resolve) => {
    requestAnimationFrame(() => resolve())
  })
}

function phaseHold(ms, overlap) {
  return Math.max(0, ms - overlap)
}

function waitMs(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

export default function CraftModule({ isActive = true }) {
  const { playSound, soundEnabled, liteMode, turboMode, musicGain } = useSettings()
  const ritualSoundTimersRef = useRef([])
  const craftRitualStopRef = useRef(null)
  const ritualEffectRef = useRef(null)
  const [slotA, setSlotA] = useState(null)
  const [slotB, setSlotB] = useState(null)
  const [ritualPhase, setRitualPhase] = useState(null)
  const [ritualRecipe, setRitualRecipe] = useState(null)
  const [ritualSlotA, setRitualSlotA] = useState(null)
  const [ritualSlotB, setRitualSlotB] = useState(null)
  const {
    kut,
    recipes,
    initialLoading,
    refreshing,
    error,
    errorCode,
    craftingPairKey,
    craftMessage,
    craftRecipe,
  } = useCraft({ isActive })

  const timing = useMemo(() => ritualTiming(turboMode, liteMode), [turboMode, liteMode])

  const twoIngredientRecipes = useMemo(
    () => recipes.filter((recipe) => recipe.ingredients.length === 2),
    [recipes],
  )

  const craftInventory = useMemo(
    () => buildCraftInventory(twoIngredientRecipes),
    [twoIngredientRecipes],
  )

  const inventoryById = useMemo(
    () => new Map(craftInventory.map((item) => [item.id, item])),
    [craftInventory],
  )

  const slotAItem = slotA ? inventoryById.get(slotA) ?? null : null
  const slotBItem = slotB ? inventoryById.get(slotB) ?? null : null
  const matchedRecipe = useMemo(
    () => findMatchingRecipe(twoIngredientRecipes, slotA, slotB),
    [twoIngredientRecipes, slotA, slotB],
  )
  const selectedPairKey = slotA && slotB ? ingredientPairKey([slotA, slotB]) : null
  const isCrafting = Boolean(craftingPairKey)
  const isRitualActive = Boolean(ritualPhase)
  const isBusy = isCrafting || isRitualActive
  const canCraft = Boolean(matchedRecipe) && !isBusy
  const performanceTier = timing.tier
  const hint = craftHint(slotA, slotB, matchedRecipe, ritualPhase)

  useEffect(() => {
    if (!isRitualActive) return undefined
    acquireScrollLock()
    return () => releaseScrollLock()
  }, [isRitualActive])

  const clearSlots = () => {
    setSlotA(null)
    setSlotB(null)
  }

  const handleInventoryPick = (itemId) => {
    if (isBusy) return

    const item = inventoryById.get(itemId)
    const owned = item?.owned ?? 0
    const inA = slotA === itemId
    const inB = slotB === itemId

    // Оба слота — один предмет: убираем оба
    if (inA && inB) {
      setSlotA(null)
      setSlotB(null)
      return
    }

    // Предмет только в слоте B: убираем из B
    if (inB) {
      setSlotB(null)
      return
    }

    // Предмет только в слоте A
    if (inA) {
      // Слот B пустой и предметов >= 2: ставим и в B
      if (!slotB && owned >= 2) {
        setSlotB(itemId)
        return
      }
      // Иначе: убираем из A (слот B занимает его место)
      setSlotA(slotB)
      setSlotB(null)
      return
    }

    // Предмета нет ни в одном слоте
    if (!slotA) {
      setSlotA(itemId)
      return
    }
    if (!slotB) {
      // Тот же предмет что в A, но только 1 шт — не ставим
      if (slotA === itemId && owned < 2) return
      setSlotB(itemId)
      return
    }
    // Оба слота заняты — заменяем B (но не если тот же предмет что в A и не хватает)
    if (slotA === itemId && owned < 2) return
    setSlotB(itemId)
  }

  const clearRitualSounds = (fadeOutMs = 900) => {
    ritualSoundTimersRef.current.forEach((timerId) => window.clearTimeout(timerId))
    ritualSoundTimersRef.current = []
    if (craftRitualStopRef.current) {
      craftRitualStopRef.current(fadeOutMs)
      craftRitualStopRef.current = null
    }
  }

  const startRitualSounds = () => {
    clearRitualSounds(100)
    playSound('craft')
    if (soundEnabled && !turboMode) {
      craftRitualStopRef.current = playCraftRitualSound({
        volume: (liteMode ? 0.32 : 0.40) * musicGain,
        fadeInMs: liteMode ? 500 : 750,
      })
    }
  }

  const handleCraft = async () => {
    if (!matchedRecipe || isBusy) return

    const recipeSnapshot = matchedRecipe
    setRitualRecipe(recipeSnapshot)
    setRitualSlotA(slotAItem)
    setRitualSlotB(slotBItem)
    startRitualSounds()

    let data = null
    const apiPromise = craftRecipe(slotA, slotB)

    try {
      if (performanceTier === 'turbo') {
        setRitualPhase('blend')
        const [apiData] = await Promise.all([apiPromise, waitMs(timing.blend)])
        data = apiData
      } else if (performanceTier === 'lite') {
        if (timing.invoke) {
          setRitualPhase('invoke')
          await waitMs(timing.invoke)
        }
        setRitualPhase('orbit')
        await waitFrame()
        const meet = await ritualEffectRef.current?.waitAlignments(timing.alignments, {
          minMs: timing.orbitMinMs,
          maxMs: 5000,
        })
        playSound('craftWhirl')
        setRitualPhase('sigil')
        playSound('craftSigil')
        await waitMs(phaseHold(timing.sigil, timing.overlap))
        data = await apiPromise
      } else {
        setRitualPhase('invoke')
        await waitMs(timing.invoke)
        setRitualPhase('orbit')
        await waitFrame()
        const meet = await ritualEffectRef.current?.waitAlignments(timing.alignments, {
          minMs: timing.orbitMinMs,
          maxMs: 6500,
        })
        playSound('craftWhirl')
        setRitualPhase('fuse')
        await ritualEffectRef.current?.runFuse(fuseDurationMs('full'), meet)
        playSound('craftWhirl')
        setRitualPhase('sigil')
        playSound('craftSigil')
        await waitMs(phaseHold(timing.sigil, timing.overlap))
        data = await apiPromise
      }
    } catch {
      clearRitualSounds()
      setRitualPhase(null)
      setRitualRecipe(null)
      return
    }

    const success = Boolean(data?.craftSuccess)
    // Плавное затихание WAV - подольше для успеха (красивый хвост), коротко для провала
    clearRitualSounds(success ? 1200 : 600)
    setRitualPhase(success ? 'success' : 'fail')
    playSound(success ? 'craftSuccess' : 'craftFail')

    await waitMs(timing.reveal)
    setRitualPhase(null)
    setRitualRecipe(null)
    setRitualSlotA(null)
    setRitualSlotB(null)
    clearSlots()
  }

  const isRitualCasting = performanceTier === 'turbo'
    ? ritualPhase === 'blend'
    : performanceTier === 'lite'
      ? ritualPhase === 'invoke' || ritualPhase === 'orbit' || ritualPhase === 'sigil'
      : ritualPhase === 'invoke' || ritualPhase === 'orbit' || ritualPhase === 'fuse' || ritualPhase === 'sigil'

  const ritualQuakeClass = performanceTier === 'full' && isRitualActive
    ? [
      ritualPhase === 'fuse' ? 'craft-module--ritual-quake craft-module--ritual-quake--fuse' : '',
      ritualPhase === 'sigil' ? 'craft-module--ritual-quake craft-module--ritual-quake--sigil' : '',
      ritualPhase === 'success' ? 'craft-module--ritual-quake craft-module--ritual-quake--success' : '',
      ritualPhase === 'fail' ? 'craft-module--ritual-quake craft-module--ritual-quake--fail' : '',
    ].filter(Boolean).join(' ')
    : ''

  const workbenchClass = [
    'craft-workbench',
    matchedRecipe && !isBusy ? 'craft-workbench--ready' : '',
    isRitualCasting ? 'craft-workbench--casting' : '',
    ritualPhase === 'success' || ritualPhase === 'fail' ? `craft-workbench--${ritualPhase}` : '',
  ].filter(Boolean).join(' ')

  return (
    <div className={['relative min-h-screen tab-theme-craft craft-module', ritualQuakeClass].filter(Boolean).join(' ')}>
      <FarmBackground />
      <TabAtmosphere variant="craft" />

      <div className="relative z-10 craft-module-shell animate-slide-up">
        <header className="craft-module-header">
          <div className="craft-module-header-main">
            <p className="craft-module-eyebrow">Алхимия · рецепты</p>
            <h1 className="craft-module-title craft-module-title--compact">
              <span aria-hidden>⚗️</span> Крафты
            </h1>
          </div>
          <KutBalance value={kut} className="craft-module-balance" />
        </header>

        {craftMessage && !isRitualActive ? (
          <p className="craft-toast craft-toast-ok" role="status">{craftMessage}</p>
        ) : null}

        {error ? (
          <p className={`craft-toast ${errorClass(errorCode)}`} role="alert">{error}</p>
        ) : null}

        {initialLoading ? (
          <div className="craft-recipes-loading">Загрузка крафта…</div>
        ) : twoIngredientRecipes.length === 0 ? (
          <div className="craft-recipes-empty">
            <span className="craft-recipes-empty-emoji" aria-hidden>⚗️</span>
            <p>Пока нет рецептов</p>
            <p className="craft-recipes-empty-hint">Загляните позже — крафты появятся вместе с новыми предметами</p>
          </div>
        ) : (
          <div className={[
            'craft-layout',
            isRitualActive ? 'craft-layout--ritual' : '',
            isRitualActive && performanceTier === 'lite' ? 'craft-layout--ritual-lite' : '',
            isRitualActive && performanceTier === 'turbo' ? 'craft-layout--ritual-turbo' : '',
            ritualPhase === 'fuse' || ritualPhase === 'sigil' ? 'craft-layout--ritual-intense' : '',
            ritualPhase === 'success' ? 'craft-layout--ritual-success' : '',
            ritualPhase === 'fail' ? 'craft-layout--ritual-fail' : '',
          ].filter(Boolean).join(' ')}>
            <VineFrame className="craft-book-frame">
              <section className="craft-book" aria-label="Книга рецептов">
                <header className="craft-book-header farm-panel-header">
                  <span className="text-lg" aria-hidden>📖</span>
                  <h2 className="text-sm font-extrabold tracking-tight text-amber-50">Книга рецептов</h2>
                </header>
                <ul className={`craft-book-list ${refreshing || isBusy ? 'craft-book-list--busy' : ''}`}>
                  {twoIngredientRecipes.map((recipe) => {
                    const recipeKey = ingredientPairKey(recipe.ingredients.map((item) => item.id))
                    const isSelected = selectedPairKey === recipeKey
                    const isMatch = matchedRecipe?.id === recipe.id
                    const isLimited = recipe.remains > 0

                    const handleRecipeClick = () => {
                      if (isBusy) return
                      const [ingA, ingB] = recipe.ingredients
                      // Одинаковый предмет в обоих слотах — проверяем что есть >= 2
                      if (ingA.id === ingB.id && (inventoryById.get(ingA.id)?.owned ?? 0) < 2) return
                      setSlotA(ingA.id)
                      setSlotB(ingB.id)
                    }

                    return (
                      <li
                        key={recipe.id}
                        className={[
                          'craft-book-item',
                          'craft-book-item--clickable',
                          isSelected ? 'craft-book-item--selected' : '',
                          isMatch ? 'craft-book-item--match' : '',
                          isMatch && isRitualCasting ? 'craft-book-item--ritual' : '',
                        ].filter(Boolean).join(' ')}
                        onClick={handleRecipeClick}
                        title="Нажми чтобы выбрать"
                      >
                        <span className="craft-book-item-formula">{formatRecipeLine(recipe)}</span>
                        <span className="craft-book-item-right">
                          {isLimited && (
                            <span className="craft-book-item-remains">×{recipe.remains}</span>
                          )}
                          <span className="craft-book-item-chance">{recipe.successPercent}%</span>
                        </span>
                      </li>
                    )
                  })}
                </ul>
              </section>
            </VineFrame>

            <div className={[
              'craft-workbench-wrap',
              isRitualActive ? `craft-workbench-wrap--ritual-${performanceTier}` : '',
            ].filter(Boolean).join(' ')}>
              {isRitualActive ? (
                <div className={[
                  'craft-ritual-overlay',
                  performanceTier === 'turbo' ? 'craft-ritual-overlay--turbo' : '',
                  performanceTier === 'lite' ? 'craft-ritual-overlay--lite-tier' : '',
                ].filter(Boolean).join(' ')} aria-hidden>
                  {performanceTier === 'full' ? <div className="craft-ritual-overlay-backdrop" /> : null}
                  {performanceTier === 'lite' ? <div className="craft-ritual-overlay-backdrop craft-ritual-overlay-backdrop--lite" /> : null}
                  <CraftRitualEffect
                    ref={ritualEffectRef}
                    phase={ritualPhase}
                    slotA={ritualSlotA ?? slotAItem}
                    slotB={ritualSlotB ?? slotBItem}
                    result={ritualRecipe?.result ?? matchedRecipe?.result}
                    recipe={ritualRecipe ?? matchedRecipe}
                    performanceTier={performanceTier}
                  />
                </div>
              ) : null}

              <section className={workbenchClass} aria-label="Верстак">
              <p className="craft-section-label">Верстак</p>
              <div className="craft-slots-row" aria-live="polite">
                <button
                  type="button"
                  className={[
                    'craft-slot-card',
                    slotAItem ? 'craft-slot-card--filled' : '',
                    ritualPhase === 'invoke' || ritualPhase === 'orbit' || ritualPhase === 'fuse' || ritualPhase === 'blend' ? 'craft-slot-card--ritual' : '',
                  ].filter(Boolean).join(' ')}
                  onClick={() => setSlotA(null)}
                  disabled={!slotA || isBusy}
                  aria-label={slotAItem ? `Слот А: ${slotAItem.name}. Нажми, чтобы очистить` : 'Слот А пуст'}
                >
                  <span className="craft-slot-card-tag">А</span>
                  <span className="craft-slot-card-emoji" aria-hidden>
                    {slotAItem?.emoji ?? '○'}
                  </span>
                  <span className="craft-slot-card-name">
                    {slotAItem?.name ?? 'Пусто'}
                  </span>
                </button>

                <span className={`craft-slots-plus ${isRitualCasting ? 'craft-slots-plus--ritual' : ''}`} aria-hidden>+</span>

                <button
                  type="button"
                  className={[
                    'craft-slot-card',
                    slotBItem ? 'craft-slot-card--filled' : '',
                    ritualPhase === 'invoke' || ritualPhase === 'orbit' || ritualPhase === 'fuse' || ritualPhase === 'blend' ? 'craft-slot-card--ritual' : '',
                  ].filter(Boolean).join(' ')}
                  onClick={() => setSlotB(null)}
                  disabled={!slotB || isBusy}
                  aria-label={slotBItem ? `Слот В: ${slotBItem.name}. Нажми, чтобы очистить` : 'Слот В пуст'}
                >
                  <span className="craft-slot-card-tag">В</span>
                  <span className="craft-slot-card-emoji" aria-hidden>
                    {slotBItem?.emoji ?? '○'}
                  </span>
                  <span className="craft-slot-card-name">
                    {slotBItem?.name ?? 'Пусто'}
                  </span>
                </button>
              </div>

              {matchedRecipe && !isRitualActive ? (
                <div className="craft-result-preview">
                  <span className="craft-result-preview-arrow" aria-hidden>→</span>
                  <span className="craft-result-preview-emoji" aria-hidden>
                    {matchedRecipe.result.emoji}
                  </span>
                  <span className="craft-result-preview-name">
                    {matchedRecipe.result.name}
                    {matchedRecipe.result.qty > 1 && (
                      <span className="craft-result-preview-qty"> ×{matchedRecipe.result.qty}</span>
                    )}
                  </span>
                  <span className="craft-result-preview-chance">{matchedRecipe.successPercent}%</span>
                </div>
              ) : null}
              </section>
            </div>

            <section className="craft-inventory" aria-label="Предметы для крафта">
              <p className="craft-section-label">
                <span aria-hidden>🎒</span> Предметы
              </p>
              {craftInventory.length === 0 ? (
                <p className="craft-inventory-empty">
                  Нет подходящих предметов в рюкзаке. Собери урожай или купи в магазине.
                </p>
              ) : (
                <div className="craft-inventory-grid">
                  {craftInventory.map((item) => {
                    const inSlotA = slotA === item.id
                    const inSlotB = slotB === item.id
                    const isPicked = inSlotA || inSlotB

                    return (
                      <button
                        key={item.id}
                        type="button"
                        className={[
                          'craft-inventory-item',
                          isPicked ? 'craft-inventory-item--picked' : '',
                        ].filter(Boolean).join(' ')}
                        disabled={isBusy}
                        onClick={() => handleInventoryPick(item.id)}
                      >
                        <span className="craft-inventory-item-emoji" aria-hidden>{item.emoji}</span>
                        <span className="craft-inventory-item-name">{item.name}</span>
                        {item.owned > 1 ? (
                          <span className="craft-inventory-item-qty">×{item.owned}</span>
                        ) : null}
                      </button>
                    )
                  })}
                </div>
              )}
            </section>

            <div className="craft-footer">
              <button
                type="button"
                className={[
                  'craft-action-btn farm-btn-primary',
                  isRitualCasting ? 'craft-action-btn--ritual' : '',
                ].filter(Boolean).join(' ')}
                disabled={!canCraft}
                onClick={handleCraft}
              >
                {isRitualCasting ? 'Ритуал…' : isCrafting ? 'Крафт…' : 'Начать ритуал'}
              </button>
              <p className={[
                'craft-footer-hint',
                canCraft ? 'craft-footer-hint--ready' : '',
                isRitualActive ? 'craft-footer-hint--silent' : '',
              ].filter(Boolean).join(' ')}>
                {hint || '\u00A0'}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
