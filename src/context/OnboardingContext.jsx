import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { completeOnboarding, startOnboarding } from '../lib/onboardingClient'
import { removeStorage, writeStorage } from '../utils/safeStorage'

const STORAGE_KEY = 'cute_interactive_guide_done'
// После закрытия приветствия тихая подсказка-пульс на вкладке «Магазин»,
// сама гаснет по таймауту или как только игрок туда заходит.
const SHOP_HINT_MS = 45000

const OnboardingContext = createContext(null)

export function OnboardingProvider({ children, activeTab }) {
  const [visible, setVisible] = useState(false)
  const [starting, setStarting] = useState(true)
  const [shopHintActive, setShopHintActive] = useState(false)

  useEffect(() => {
    let cancelled = false
    startOnboarding()
      .then((state) => {
        if (cancelled) return
        if (state?.onboarding?.done) {
          writeStorage(STORAGE_KEY, 'true')
        } else {
          removeStorage(STORAGE_KEY)
          setVisible(true)
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setStarting(false)
      })
    return () => { cancelled = true }
  }, [])

  const dismiss = useCallback(() => {
    setVisible(false)
    setShopHintActive(true)
    completeOnboarding({ skipped: false })
      .then(() => writeStorage(STORAGE_KEY, 'true'))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!shopHintActive) return undefined
    const timer = window.setTimeout(() => setShopHintActive(false), SHOP_HINT_MS)
    return () => window.clearTimeout(timer)
  }, [shopHintActive])

  useEffect(() => {
    if (shopHintActive && activeTab === 'shop') setShopHintActive(false)
  }, [activeTab, shopHintActive])

  const pulseTab = shopHintActive ? 'shop' : null

  const value = useMemo(
    () => ({ visible, starting, dismiss, pulseTab }),
    [visible, starting, dismiss, pulseTab],
  )

  return (
    <OnboardingContext.Provider value={value}>{children}</OnboardingContext.Provider>
  )
}

export function useOnboarding() {
  const ctx = useContext(OnboardingContext)
  if (!ctx) throw new Error('useOnboarding must be used within OnboardingProvider')
  return ctx
}

export function useOnboardingOptional() {
  return useContext(OnboardingContext)
}
