import { useCallback, useEffect, useState } from 'react'
import { PlayerSyncProvider } from './context/PlayerSyncContext'
import { OnboardingProvider, useOnboardingOptional } from './context/OnboardingContext'
import FarmModule from './components/FarmModule'
import CraftModule from './components/CraftModule'
import TradeModule from './components/TradeModule'
import GiveawaysModule from './components/GiveawaysModule'
import ChestModule from './components/ChestModule'
import InventoryModule from './components/InventoryModule'
import QuestsModule from './components/QuestsModule'
import SettingsModule from './components/SettingsModule'
import ProfileModule from './components/ProfileModule'
import TabBar from './components/TabBar'
import Onboarding from './components/Onboarding'
import BackgroundMusic from './components/BackgroundMusic'
import MaintenanceScreen from './components/MaintenanceScreen'
import AppLoadingScreen from './components/AppLoadingScreen'
import BannedScreen from './components/BannedScreen'
import SaleNotificationLayer from './components/SaleNotificationLayer'
import ShopPurchaseGuideLayer from './components/ShopPurchaseGuideLayer'
import MarketPurchaseGuideLayer from './components/MarketPurchaseGuideLayer'
import ItemGuideToastLayer from './components/ItemGuideToastLayer'
import { useEquippedCosmetics } from './hooks/useEquippedCosmetics'
import { useSwipeTabs } from './hooks/useSwipeTabs'
import { usePresencePing } from './hooks/usePresencePing'
import { syncSession } from './lib/sessionClient'
import { canAuthenticate, getStartTab } from './lib/telegram'
import { resolveStartTab } from './utils/tradeNav'
import { fetchAppStatus } from './lib/apiClient'

export default function App() {
  const [maintenance, setMaintenance] = useState(false)
  const [statusLoading, setStatusLoading] = useState(true)
  const [banned, setBanned] = useState(false)
  const [bannedMessage, setBannedMessage] = useState('')

  useEffect(() => {
    let cancelled = false
    fetchAppStatus()
      .then((status) => {
        if (!cancelled) setMaintenance(Boolean(status.maintenance))
      })
      .catch((err) => {
        if (!cancelled) {
          if (err?.status === 403) {
            setBanned(true)
            setBannedMessage(err.message || '')
          } else {
            setMaintenance(false)
          }
        }
      })
      .finally(() => { if (!cancelled) setStatusLoading(false) })
    return () => { cancelled = true }
  }, [])

  // Глобальный перехват 403 от любого API запроса
  useEffect(() => {
    const handler = (e) => {
      const err = e.detail
      if (err?.status === 403 && !banned) {
        setBanned(true)
        setBannedMessage(err.message || '')
      }
    }
    window.addEventListener('api:forbidden', handler)
    return () => window.removeEventListener('api:forbidden', handler)
  }, [banned])

  // Только реальные техработы из /api/status не любой HTTP 503
  useEffect(() => {
    const handler = (event) => {
      const err = event.detail
      if (err?.code === 'maintenance') {
        setMaintenance(true)
      }
    }
    window.addEventListener('api:maintenance', handler)
    return () => window.removeEventListener('api:maintenance', handler)
  }, [])

  usePresencePing({ enabled: !statusLoading && !maintenance && !banned })

  useEffect(() => {
    if (statusLoading || maintenance || banned || !canAuthenticate()) return
    syncSession().catch(() => {})
  }, [statusLoading, maintenance, banned])

  if (banned) return <BannedScreen message={bannedMessage} />

  if (statusLoading) {
    return <AppLoadingScreen />
  }

  if (maintenance) {
    return <MaintenanceScreen />
  }

  return (
    <PlayerSyncProvider>
      <AppWithOnboarding />
    </PlayerSyncProvider>
  )
}

function AppWithOnboarding() {
  const [tab, setTab] = useState(() => resolveStartTab(getStartTab() ?? 'farm').tab)
  const [tradeSegment, setTradeSegment] = useState(() => resolveStartTab(getStartTab() ?? 'farm').tradeSegment)

  return (
    <OnboardingProvider activeTab={tab}>
      <AppShell
        tab={tab}
        setTab={setTab}
        tradeSegment={tradeSegment}
        setTradeSegment={setTradeSegment}
      />
    </OnboardingProvider>
  )
}

function AppShell({ tab, setTab, tradeSegment, setTradeSegment }) {
  const onboarding = useOnboardingOptional()
  const blockSwipe = Boolean(onboarding?.visible)
  const { equipped } = useEquippedCosmetics()
  const [shopSearch, setShopSearch] = useState('')
  const [shopItemId, setShopItemId] = useState('')
  const [shopHighlightOnly, setShopHighlightOnly] = useState(false)
  const [marketSearch, setMarketSearch] = useState('')
  const [marketItemId, setMarketItemId] = useState('')
  const [marketHighlightOnly, setMarketHighlightOnly] = useState(false)

  const handleGuideNavigateShop = useCallback((item) => {
    setShopSearch(item?.name ?? '')
    setShopItemId(item?.id ? String(item.id) : '')
    setShopHighlightOnly(true)
    setTab('trade')
    setTradeSegment('shop')
  }, [setTab, setTradeSegment])

  const handleGuideNavigateMarket = useCallback((item) => {
    setMarketSearch(item?.name ?? '')
    setMarketItemId(item?.itemId ? String(item.itemId) : '')
    setMarketHighlightOnly(true)
    setTab('trade')
    setTradeSegment('market')
  }, [setTab, setTradeSegment])

  useSwipeTabs({ activeTab: tab, onChange: setTab, enabled: !blockSwipe })

  useEffect(() => {
    const handler = (e) => {
      const search = e.detail?.search ?? ''
      const itemId = e.detail?.itemId ?? ''
      setShopSearch(search)
      setShopItemId(itemId ? String(itemId) : '')
      setShopHighlightOnly(Boolean(e.detail?.highlightOnly))
      setTab('trade')
      setTradeSegment('shop')
    }
    window.addEventListener('farm:go-to-shop', handler)
    return () => window.removeEventListener('farm:go-to-shop', handler)
  }, [setTab, setTradeSegment])

  useEffect(() => {
    const handler = (e) => {
      const search = e.detail?.search ?? ''
      const itemId = e.detail?.itemId ?? ''
      setMarketSearch(search)
      setMarketItemId(itemId ? String(itemId) : '')
      setMarketHighlightOnly(Boolean(e.detail?.highlightOnly))
      setTab('trade')
      setTradeSegment('market')
    }
    window.addEventListener('farm:go-to-market', handler)
    return () => window.removeEventListener('farm:go-to-market', handler)
  }, [setTab, setTradeSegment])

  return (
    <div className={`app-shell${equipped.background ? ' app-has-bg' : ''}`} data-active-tab={tab}>
      <BackgroundMusic />
      <Onboarding />
      <SaleNotificationLayer />
      <ShopPurchaseGuideLayer onNavigateShop={handleGuideNavigateShop} />
      <MarketPurchaseGuideLayer onNavigateMarket={handleGuideNavigateMarket} />
      <ItemGuideToastLayer />
      <main className="app-main">
        <div className={tab === 'farm' ? '' : 'hidden'} aria-hidden={tab !== 'farm'}>
          <FarmModule isActive={tab === 'farm'} />
        </div>
        <div className={tab === 'inventory' ? '' : 'hidden'} aria-hidden={tab !== 'inventory'}>
          <InventoryModule isActive={tab === 'inventory'} />
        </div>
        <div className={tab === 'craft' ? '' : 'hidden'} aria-hidden={tab !== 'craft'}>
          <CraftModule isActive={tab === 'craft'} />
        </div>
        <div className={tab === 'quests' ? '' : 'hidden'} aria-hidden={tab !== 'quests'}>
          <QuestsModule isActive={tab === 'quests'} />
        </div>
        <div className={tab === 'trade' ? '' : 'hidden'} aria-hidden={tab !== 'trade'}>
          <TradeModule
            isActive={tab === 'trade'}
            segment={tradeSegment}
            onSegmentChange={setTradeSegment}
            shopSearch={shopSearch}
            shopItemId={shopItemId}
            shopHighlightOnly={shopHighlightOnly}
            onShopSearchUsed={() => {
              setShopSearch('')
              setShopItemId('')
              setShopHighlightOnly(false)
            }}
            marketSearch={marketSearch}
            marketItemId={marketItemId}
            marketHighlightOnly={marketHighlightOnly}
            onMarketSearchUsed={() => {
              setMarketSearch('')
              setMarketItemId('')
              setMarketHighlightOnly(false)
            }}
          />
        </div>
        <div className={tab === 'giveaways' ? '' : 'hidden'} aria-hidden={tab !== 'giveaways'}>
          <GiveawaysModule isActive={tab === 'giveaways'} />
        </div>
        <div className={tab === 'chests' ? '' : 'hidden'} aria-hidden={tab !== 'chests'}>
          <ChestModule isActive={tab === 'chests'} />
        </div>
        <div className={tab === 'profile' ? '' : 'hidden'} aria-hidden={tab !== 'profile'}>
          <ProfileModule isActive={tab === 'profile'} />
        </div>
        <div className={tab === 'settings' ? '' : 'hidden'} aria-hidden={tab !== 'settings'}>
          <SettingsModule />
        </div>
      </main>
      <TabBar active={tab} onChange={setTab} />
    </div>
  )
}
