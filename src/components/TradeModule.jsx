import FarmBackground from './FarmBackground'
import TabAtmosphere from './TabAtmosphere'
import KutBalance from './KutBalance'
import DonateModal from './DonateModal'
import ExchangeModule from './ExchangeModule'
import MarketplaceModule from './MarketplaceModule'
import { useContextualDonate } from '../hooks/useContextualDonate'
import { usePlayerSync } from '../context/PlayerSyncContext'
import '../styles/trade.css'

const SEGMENTS = [
  { id: 'shop', label: 'Магазин' },
  { id: 'market', label: 'Биржа' },
]

export default function TradeModule({
  isActive = true,
  segment,
  onSegmentChange,
  shopSearch = '',
  shopItemId = '',
  shopHighlightOnly = false,
  onShopSearchUsed,
  marketSearch = '',
  marketItemId = '',
  marketHighlightOnly = false,
  onMarketSearchUsed,
}) {
  const { kut } = usePlayerSync()
  const { donateOpen, donateContext, openDonate, closeDonate } = useContextualDonate()

  const theme = segment === 'shop' ? 'shop' : 'market'

  return (
    <div className={`relative min-h-screen tab-theme-${theme} trade-module`} aria-hidden={!isActive}>
      <FarmBackground />
      <TabAtmosphere variant={theme} />

      <div className="relative z-10 trade-shell py-4 pb-2 animate-slide-up">
        <header className="trade-header">
          <div className="trade-header-main">
            <p className="trade-header-eyebrow">Cute</p>
            <h1 className="trade-header-title">Торговля</h1>
          </div>
          <KutBalance value={kut ?? 0} className="trade-header-balance" onDonate={openDonate} />
        </header>

        <div className="trade-subtabs" role="tablist" aria-label="Разделы торговли">
          {SEGMENTS.map((s) => (
            <button
              key={s.id}
              type="button"
              role="tab"
              aria-selected={segment === s.id}
              className={`trade-subtab${segment === s.id ? ' trade-subtab-active' : ''}`}
              onClick={() => onSegmentChange(s.id)}
            >
              {s.label}
            </button>
          ))}
        </div>

        {segment === 'shop' ? (
          <ExchangeModule
            embedded
            isActive={isActive}
            initialSearch={shopSearch}
            initialItemId={shopItemId}
            initialHighlightOnly={shopHighlightOnly}
            onSearchUsed={onShopSearchUsed}
          />
        ) : (
          <MarketplaceModule
            embedded
            isActive={isActive}
            initialSearch={marketSearch}
            initialItemId={marketItemId}
            initialHighlightOnly={marketHighlightOnly}
            onSearchUsed={onMarketSearchUsed}
          />
        )}
      </div>

      <DonateModal isOpen={donateOpen} onClose={closeDonate} context={donateContext} />
    </div>
  )
}
