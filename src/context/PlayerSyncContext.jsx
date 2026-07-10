import { createContext, useCallback, useContext, useMemo, useState } from 'react'

const PlayerSyncContext = createContext(null)

export function PlayerSyncProvider({ children }) {
  const [kut, setKut] = useState(null)
  const [inventoryTick, setInventoryTick] = useState(0)

  const syncFromShop = useCallback((data) => {
    if (data?.kut != null) {
      setKut(data.kut)
    }
    if (data?.purchased || data?.player) {
      setInventoryTick((value) => value + 1)
    }
  }, [])

  const syncFromMarket = useCallback((data) => {
    if (data?.kut != null) {
      setKut(data.kut)
    }
    if (data?.purchased || data?.listed || data?.player) {
      setInventoryTick((value) => value + 1)
    }
  }, [])

  const syncFromCraft = useCallback((data) => {
    if (data?.kut != null) {
      setKut(data.kut)
    }
    if (data?.player || data?.craftSuccess != null) {
      setInventoryTick((value) => value + 1)
    }
  }, [])

  const syncFromFarm = useCallback((nextKut) => {
    if (nextKut != null) {
      setKut(nextKut)
    }
  }, [])

  const syncFromNotification = useCallback(({ balance, payout } = {}) => {
    if (balance != null) {
      setKut(balance)
      return
    }
    if (payout != null) {
      setKut((prev) => (prev != null ? prev + payout : payout))
    }
    setInventoryTick((value) => value + 1)
  }, [])

  const value = useMemo(
    () => ({
      kut,
      inventoryTick,
      syncFromShop,
      syncFromMarket,
      syncFromCraft,
      syncFromFarm,
      syncFromNotification,
    }),
    [inventoryTick, kut, syncFromCraft, syncFromFarm, syncFromMarket, syncFromNotification, syncFromShop],
  )

  return (
    <PlayerSyncContext.Provider value={value}>
      {children}
    </PlayerSyncContext.Provider>
  )
}

export function usePlayerSync() {
  const context = useContext(PlayerSyncContext)
  if (!context) {
    throw new Error('usePlayerSync must be used within PlayerSyncProvider')
  }
  return context
}
