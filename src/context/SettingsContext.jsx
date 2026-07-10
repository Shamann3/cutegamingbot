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



const SOUND_STORAGE_KEY = 'cute_sound_enabled'



function readPerformanceMode() {

  const stored = readStorage(PERF_MODE_STORAGE_KEY)

  if (PERF_MODE_ORDER.includes(stored)) return stored



  const legacyLite = readStorage(LITE_MODE_LEGACY_KEY)

  if (legacyLite === 'true') return PERF_MODES.LITE



  return PERF_MODES.FULL

}



const SettingsContext = createContext(null)



export function SettingsProvider({ children }) {

  const [soundEnabled, setSoundEnabled] = useState(() => {

    const stored = readStorage(SOUND_STORAGE_KEY)

    return stored === null ? true : stored === 'true'

  })



  const [performanceMode, setPerformanceMode] = useState(readPerformanceMode)

  const [musicVolume, setMusicVolume] = useState(readMusicVolumePercent)

  const musicGain = musicGainFromPercent(musicVolume)

  useEffect(() => {

    const lite = isLiteOrAbove(performanceMode)

    const turbo = isTurboMode(performanceMode)

    document.documentElement.classList.toggle('cute-lite-mode', lite)

    document.documentElement.classList.toggle('cute-turbo-mode', turbo)

  }, [performanceMode])



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

      toggleSound,

      setMusicVolume: setMusicVolumePercent,

      cyclePerformanceMode,

      setPerformanceMode: setPerformanceModeDirect,

      toggleLiteMode: cyclePerformanceMode,

      playSound,

    }),

    [soundEnabled, musicVolume, musicGain, performanceMode, liteMode, turboMode, toggleSound, setMusicVolumePercent, cyclePerformanceMode, setPerformanceModeDirect, playSound],

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


