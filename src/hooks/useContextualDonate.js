import { useCallback, useState } from 'react'
import { buildDonateContext } from '../utils/contextualDonate'

export function useContextualDonate() {
  const [donateOpen, setDonateOpen] = useState(false)
  const [donateContext, setDonateContext] = useState(null)

  const openDonate = useCallback(() => {
    setDonateContext(null)
    setDonateOpen(true)
  }, [])

  const openContextualDonate = useCallback(({ balance, neededCost, actionLabel }) => {
    setDonateContext(buildDonateContext({ balance, neededCost, actionLabel }))
    setDonateOpen(true)
  }, [])

  const closeDonate = useCallback(() => {
    setDonateOpen(false)
  }, [])

  return {
    donateOpen,
    donateContext,
    openDonate,
    openContextualDonate,
    closeDonate,
  }
}
