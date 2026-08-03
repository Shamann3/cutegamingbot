import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import {
  isLiteOrAbove,
  isTurboMode,
  LITE_MODE_LEGACY_KEY,
  nextPerfMode,
  PERF_MODE_ORDER,
  PERF_MODE_STORAGE_KEY,
  PERF_MODES,
} from '../constants/performance'
import { farmSounds } from '../utils/sounds'
import {
  MUSIC_VOLUME_STORAGE_KEY,
  musicGainFromPercent,
  readMusicVolumePercent,
} from '../constants/musicVolume'
import { readStorage, writeStorage } from '../utils/safeStorage'
import { bindMobilePerfClass } from '../utils/devicePerf'
import {
  resolveSeason,
  SEASON_MODE_ORDER,
  SEASON_MODES,
  SEASON_STORAGE_KEY,
} from '../constants/season'

const SOUND_STORAGE_KEY = 'cute_sound_enabled'
const SettingsContext = createContext(null)

function readPerformanceMode() {
  const stored = readStorage(PERF_MODE_STORAGE_KEY)
  if (PERF_MODE_ORDER.includes(stored)) return stored

  const legacyLite = readStorage(LITE_MODE_LEGACY_KEY)
  if (legacyLite === 'true') return PERF_MODES.LITE

  return PERF_MODES.FULL
}

function readSeasonMode() {
  const stored = readStorage(SEASON_STORAGE_KEY)
  if (SEASON_MODE_ORDER.includes(stored)) return stored
  return SEASON_MODES.AUTO
}

export function SettingsProvider({ children }) {
  const [soundEnabled, setSoundEnabled] = useState(() => {
    const stored = readStorage(SOUND_STORAGE_KEY)
    return stored === null ? true : stored === 'true'
  })

  const [performanceMode, setPerformanceMode] = useState(readPerformanceMode)
  const [musicVolume, setMusicVolume] = useState(readMusicVolumePercent)
  const [seasonMode, setSeasonModeState] = useState(readSeasonMode)
  const [seasonTick, setSeasonTick] = useState(0)
  const musicGain = musicGainFromPercent(musicVolume)

  const season = useMemo(
    () => resolveSeason(seasonMode),
    [seasonMode, seasonTick],
  )

  useEffect(() => {
    const lite = isLiteOrAbove(performanceMode)
    const turbo = isTurboMode(performanceMode)
    document.documentElement.classList.toggle('cute-lite-mode', lite)
    document.documentElement.classList.toggle('cute-turbo-mode', turbo)
  }, [performanceMode])

  useEffect(() => {
    document.documentElement.dataset.season = season
    document.documentElement.classList.toggle('cute-season-spring', season === 'spring')
    document.documentElement.classList.toggle('cute-season-summer', season === 'summer')
    document.documentElement.classList.toggle('cute-season-autumn', season === 'autumn')
    document.documentElement.classList.toggle('cute-season-winter', season === 'winter')
  }, [season])

  // Пересчёт авто-сезона при смене суток / возврате во вкладку
  useEffect(() => {
    if (seasonMode !== SEASON_MODES.AUTO) return undefined
    const refresh = () => setSeasonTick((n) => n + 1)
    const onVis = () => {
      if (document.visibilityState === 'visible') refresh()
    }
    document.addEventListener('visibilitychange', onVis)
    const id = window.setInterval(refresh, 60 * 60 * 1000)
    return () => {
      document.removeEventListener('visibilitychange', onVis)
      window.clearInterval(id)
    }
  }, [seasonMode])

  useEffect(() => bindMobilePerfClass(), [])

  const toggleSound = useCallback(() => {
    setSoundEnabled((prev) => {
      const next = !prev
      writeStorage(SOUND_STORAGE_KEY, String(next))
      return next
    })
  }, [])

  const setMusicVolumePercent = useCallback((value) => {
    const next = Math.max(0, Math.min(100, Math.round(Number(value) || 0)))
    setMusicVolume(next)
    writeStorage(MUSIC_VOLUME_STORAGE_KEY, String(next))
  }, [])

  const cyclePerformanceMode = useCallback(() => {
    setPerformanceMode((prev) => {
      const next = nextPerfMode(prev)
      writeStorage(PERF_MODE_STORAGE_KEY, next)
      return next
    })
  }, [])

  const setPerformanceModeDirect = useCallback((mode) => {
    if (!PERF_MODE_ORDER.includes(mode)) return
    setPerformanceMode(mode)
    writeStorage(PERF_MODE_STORAGE_KEY, mode)
  }, [])

  const setSeasonMode = useCallback((mode) => {
    if (!SEASON_MODE_ORDER.includes(mode)) return
    setSeasonModeState(mode)
    writeStorage(SEASON_STORAGE_KEY, mode)
  }, [])

  const playSound = useCallback(
    (name) => {
      if (!soundEnabled) return
      const fn = farmSounds[name]
      if (fn) fn()
    },
    [soundEnabled],
  )

  const liteMode = isLiteOrAbove(performanceMode)
  const turboMode = isTurboMode(performanceMode)

  const value = useMemo(
    () => ({
      soundEnabled,
      musicVolume,
      musicGain,
      performanceMode,
      liteMode,
      turboMode,
      seasonMode,
      season,
      toggleSound,
      setMusicVolume: setMusicVolumePercent,
      cyclePerformanceMode,
      setPerformanceMode: setPerformanceModeDirect,
      toggleLiteMode: cyclePerformanceMode,
      setSeasonMode,
      playSound,
    }),
    [
      soundEnabled,
      musicVolume,
      musicGain,
      performanceMode,
      liteMode,
      turboMode,
      seasonMode,
      season,
      toggleSound,
      setMusicVolumePercent,
      cyclePerformanceMode,
      setPerformanceModeDirect,
      setSeasonMode,
      playSound,
    ],
  )

  return (
    <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>
  )
}

export function useSettings() {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider')
  return ctx
}
