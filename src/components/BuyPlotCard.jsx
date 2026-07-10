import { formatKut } from '../utils/formatKut'
import { buildDonateContext, calcShortfall, suggestDonateAmount } from '../utils/contextualDonate'
import VineFrame from './VineFrame'

export default function BuyPlotCard({ price, kut, isBusy, onBuy, onContextualDonate }) {
  const canAfford = kut >= price
  const suggestedTopUp = suggestDonateAmount(kut, price)

  const handlePrimaryClick = () => {
    if (canAfford) {
      onBuy?.()
      return
    }
    onContextualDonate?.(buildDonateContext({ balance: kut, neededCost: price, actionLabel: 'Чтобы купить грядку' }))
  }

  return (
    <VineFrame dashed>
      <article className="flex flex-col">
      <button
        type="button"
        className="farm-soil-panel farm-buy-plot-trigger"
        disabled={isBusy}
        onClick={handlePrimaryClick}
        aria-label={canAfford ? 'Купить грядку' : 'Пополнить баланс'}
      >
        <div className="farm-soil-inner farm-buy-plot-inner">
          <span className="farm-buy-plot-icon" aria-hidden>
            ✚
          </span>
          <p className="farm-buy-plot-label">
            Ещё одна грядка
          </p>
        </div>
      </button>

      <div className="farm-panel-body">
        <p className="farm-buy-plot-eyebrow">
          Расширьте ферму
        </p>
        <p className="farm-buy-plot-price">
          {formatKut(price)} КУТ
        </p>
        <button
          type="button"
          className={`farm-btn-buy farm-buy-plot-btn ${!canAfford ? 'farm-btn-buy--donate' : ''}`}
          disabled={isBusy}
          onClick={handlePrimaryClick}
        >
          {canAfford ? 'Купить грядку' : `Пополнить ${formatKut(suggestedTopUp)} КУТ`}
        </button>
        {!canAfford && (
          <p className="farm-buy-plot-shortfall">
            Не хватает {formatKut(calcShortfall(kut, price))} КУТ
          </p>
        )}
      </div>
      </article>
    </VineFrame>
  )
}
