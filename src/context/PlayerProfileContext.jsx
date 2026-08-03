import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import PlayerProfileModal from '../components/PlayerProfileModal'

const PlayerProfileContext = createContext(null)

export function PlayerProfileProvider({ children }) {
  const [userId, setUserId] = useState(null)

  const openProfile = useCallback((id) => {
    const n = Number(id)
    if (!Number.isFinite(n) || n <= 0) return
    setUserId(n)
  }, [])

  const closeProfile = useCallback(() => setUserId(null), [])

  const value = useMemo(
    () => ({ openProfile, closeProfile, profileUserId: userId }),
    [openProfile, closeProfile, userId],
  )

  return (
    <PlayerProfileContext.Provider value={value}>
      {children}
      <PlayerProfileModal
        userId={userId}
        isOpen={Boolean(userId)}
        onClose={closeProfile}
      />
    </PlayerProfileContext.Provider>
  )
}

export function usePlayerProfile() {
  return useContext(PlayerProfileContext)
}

export function useOpenPlayerProfile() {
  const ctx = usePlayerProfile()
  return ctx?.openProfile ?? (() => {})
}
