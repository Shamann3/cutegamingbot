import { useCallback, useEffect, useState } from 'react'
import { useSettings } from '../context/SettingsContext'
import ShopPurchaseModal from './ShopPurchaseModal'
import DonateModal from './DonateModal'
import { buyShopItem } from '../lib/shopClient'
import { usePlayerSync } from '../context/PlayerSyncContext'
import { useContextualDonate } from '../hooks/useContextualDonate'

export default function ShopPurchaseGuideLayer({ onNavigateShop }) {
  const { playSound } = useSettings()
  const { kut: sharedKut, syncFromShop } = usePlayerSync()
  const [item, setItem] = useState(null)
  const [kutOverride, setKutOverride] = useState(null)
  const [buying, setBuying] = useState(false)
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
      onNavigateShop?.(guideItem)
    }
    window.addEventListener('farm:open-shop-purchase', handler)
    return () => window.removeEventListener('farm:open-shop-purchase', handler)
  }, [onNavigateShop])

  const handleClose = useCallback(() => {
    setItem(null)
    setKutOverride(null)
  }, [])

  const handleConfirm = async (itemId, quantity) => {
    setBuying(true)
    try {
      const result = await buyShopItem(itemId, {
        quantity,
        search: item?.name ?? '',
      })
      syncFromShop?.(result)
      if (result?.kut != null) setKutOverride(Number(result.kut))
      playSound('harvest')
      const purchased = result?.purchased
      window.dispatchEvent(new CustomEvent('farm:purchase-complete', {
        detail: {
          name: purchased?.name || item?.name || 'Саженец',
          emoji: purchased?.emoji || item?.emoji || '🌱',
          itemId: purchased?.id || itemId,
          quantity: Number(purchased?.quantity ?? quantity ?? 1),
        },
      }))
      handleClose()
    } catch {
      // ошибка в модалке / API
    } finally {
      setBuying(false)
    }
  }

  return (
    <>
      <ShopPurchaseModal
        item={item}
        kut={kut}
        isOpen={Boolean(item)}
        isBuying={buying}
        onClose={handleClose}
        onConfirm={handleConfirm}
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
