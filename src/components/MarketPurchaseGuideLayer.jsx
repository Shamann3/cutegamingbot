import { useCallback, useEffect, useState } from 'react'
import { useSettings } from '../context/SettingsContext'
import MarketListingModal from './MarketListingModal'
import DonateModal from './DonateModal'
import { buyMarketListing } from '../lib/marketClient'
import { usePlayerSync } from '../context/PlayerSyncContext'
import { useContextualDonate } from '../hooks/useContextualDonate'

export default function MarketPurchaseGuideLayer({ onNavigateMarket }) {
  const { playSound } = useSettings()
  const { kut: sharedKut, syncFromMarket } = usePlayerSync()
  const [item, setItem] = useState(null)
  const [kutOverride, setKutOverride] = useState(null)
  const [busy, setBusy] = useState(false)
  const {
    donateOpen,
    donateContext,
    openContextualDonate,
    closeDonate,
  } = useContextualDonate()

  const kut = kutOverride ?? sharedKut ?? 0

  useEffect(() => {
    const handler = (event) => {
      const { item: guideItem, kut: guideKut } = event.detail ?? {}
      if (!guideItem) return
      setItem(guideItem)
      setKutOverride(guideKut != null ? Number(guideKut) : null)
      onNavigateMarket?.(guideItem)
    }
    window.addEventListener('farm:open-market-purchase', handler)
    return () => window.removeEventListener('farm:open-market-purchase', handler)
  }, [onNavigateMarket])

  const handleClose = useCallback(() => {
    setItem(null)
    setKutOverride(null)
  }, [])

  const handleBuy = async (listingId, quantity) => {
    setBusy(true)
    try {
      const result = await buyMarketListing(listingId, {
        quantity,
        search: item?.name ?? '',
      })
      syncFromMarket?.(result)
      if (result?.kut != null) setKutOverride(Number(result.kut))
      playSound('harvest')
      handleClose()
    } catch {
      // ошибка в API
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <MarketListingModal
        item={item}
        kut={kut}
        isOpen={Boolean(item)}
        isBusy={busy}
        onClose={handleClose}
        onConfirmBuy={handleBuy}
        onContextualDonate={(payload) => {
          openContextualDonate(payload)
          handleClose()
        }}
      />
      <DonateModal
        isOpen={donateOpen}
        onClose={closeDonate}
        context={donateContext}
      />
    </>
  )
}
