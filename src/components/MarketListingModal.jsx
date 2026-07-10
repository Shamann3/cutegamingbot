import { useEffect, useState } from 'react'
import { formatKut } from '../utils/formatKut'
import { calcMarketCommission, calcMarketSellerPayout, listingUnitPrice } from '../lib/marketClient'
import { useEscapeClose, useEnterConfirm } from '../hooks/useEscapeClose'
import ContextualDonatePrompt from './ContextualDonatePrompt'
import { suggestDonateAmount } from '../utils/contextualDonate'
import Portal from './Portal'
import SellerNameButton from './SellerNameButton'

export default function MarketListingModal({
  item,
  kut,
  isOpen,
  isBusy,
  commissionPercent = 7,
  onClose,
  onConfirmBuy,
  onCancelListing,
  onOpenSellerProfile,
  onContextualDonate,
}) {
  const [quantityText, setQuantityText] = useState('1')

  useEffect(() => {
    setQuantityText('1')
  }, [item?.id])

  useEscapeClose(isOpen && Boolean(item), onClose, { enabled: !isBusy })

  const balance = Number(kut) || 0
  const price = item ? listingUnitPrice(item) : 0
  const maxByStock = item ? Math.max(0, item.quantity) : 0
  const maxQty = Math.min(maxByStock, 99)

  const parsedQuantity = Number.parseInt(quantityText, 10)
  const hasValidQuantity = Number.isFinite(parsedQuantity) && parsedQuantity >= 1
  const quantity = hasValidQuantity ? Math.min(parsedQuantity, maxQty) : 1
  const totalCost = price * (hasValidQuantity ? quantity : 0)
  const grossIfSold = price * (item?.quantity ?? 0)
  const commissionIfSold = calcMarketCommission(grossIfSold, commissionPercent)
  const payoutIfSold = calcMarketSellerPayout(grossIfSold, commissionPercent)
  const canAfford = balance >= totalCost
  const outOfStock = !item || maxByStock < 1
  const needsTopUp = !item?.isMine && !outOfStock && hasValidQuantity && !canAfford

  const confirmDisabled = isBusy || outOfStock || item?.isMine
    || (!needsTopUp && !canAfford)
    || !hasValidQuantity || quantity < 1

  // Хук ДО раннего return
  useEnterConfirm(isOpen && Boolean(item) && !confirmDisabled, () => {
    if (needsTopUp && onContextualDonate) {
      onContextualDonate({ balance, neededCost: totalCost, actionLabel })
    } else if (!confirmDisabled) {
      onConfirmBuy(item.id, quantity)
    }
  }, { enabled: !isBusy })

  const actionLabel = item ? `Купить «${item.name}» на бирже` : 'Покупка на бирже'
  const suggestedTopUp = needsTopUp ? suggestDonateAmount(balance, totalCost) : 0

  let confirmLabel = 'Купить'
  if (isBusy) confirmLabel = 'Оформляем…'
  else if (item?.isMine) confirmLabel = 'Это ваш лот'
  else if (outOfStock) confirmLabel = 'Нет в наличии'
  else if (needsTopUp) confirmLabel = `Пополнить ${formatKut(suggestedTopUp)} КУТ`

  if (!isOpen || !item) return null

  const setQuantityValue = (next) => {
    setQuantityText(String(Math.max(1, Math.min(next, maxQty))))
  }

  const handleConfirmBuy = () => {
    if (needsTopUp && onContextualDonate) {
      onContextualDonate({ balance, neededCost: totalCost, actionLabel })
      return
    }
    if (confirmDisabled) return
    onConfirmBuy(item.id, quantity)
  }

  return (
    <Portal lockScroll>
      <div className="shop-modal-root" role="presentation" onClick={onClose}>
        <div
          className="shop-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="market-modal-title"
          onClick={(event) => event.stopPropagation()}
        >
          <button type="button" className="shop-modal-close" onClick={onClose} aria-label="Закрыть">
            ✕
          </button>

          <div className="shop-modal-hero">
            <span className="shop-modal-emoji" aria-hidden>{item.emoji}</span>
          </div>

          <div className="shop-modal-content">
            <p className="shop-modal-category">{item.categoryLabel}</p>
            <h2 id="market-modal-title" className="shop-modal-title">{item.name}</h2>
            <p className="market-modal-seller">
              Продавец:{' '}
              <SellerNameButton
                sellerId={item.sellerId}
                sellerLabel={item.sellerLabel}
                sellerName={item.sellerName}
                onOpenProfile={onOpenSellerProfile}
              />
            </p>
            {item.bio || item.description ? (
              <div className="shop-modal-bio">
                <p className="shop-modal-bio-label">О предмете</p>
                <p className="shop-modal-description">{item.bio || item.description}</p>
              </div>
            ) : null}

            {!item.isMine ? (
              <div className="shop-modal-quantity">
                <div className="shop-modal-quantity-head">
                  <span className="shop-modal-quantity-label">Сколько купить</span>
                  <span className="shop-modal-quantity-limit">доступно: {formatKut(maxQty)}</span>
                </div>
                <div className="shop-modal-quantity-stepper">
                  <button
                    type="button"
                    className="shop-modal-qty-step"
                    onClick={() => setQuantityValue(quantity - 1)}
                    disabled={quantity <= 1}
                  >
                    −
                  </button>
                  <input
                    type="text"
                    inputMode="numeric"
                    className="shop-modal-qty-input"
                    value={quantityText}
                    onChange={(e) => {
                      const digits = e.target.value.replace(/\D/g, '')
                      setQuantityText(digits === '' ? '' : String(Math.min(Number(digits), maxQty)))
                    }}
                    onBlur={() => setQuantityText(String(quantity))}
                  />
                  <button
                    type="button"
                    className="shop-modal-qty-step"
                    onClick={() => setQuantityValue(quantity + 1)}
                    disabled={quantity >= maxQty}
                  >
                    +
                  </button>
                  <button
                    type="button"
                    className="shop-modal-qty-max"
                    onClick={() => setQuantityValue(maxQty)}
                    disabled={maxQty < 1}
                  >
                    Макс
                  </button>
                </div>
              </div>
            ) : null}

            {!item.isMine && needsTopUp ? (
              <ContextualDonatePrompt
                balance={balance}
                neededCost={totalCost}
                actionLabel={actionLabel}
                onDonate={onContextualDonate}
              />
            ) : null}

            <div className="shop-modal-stats">
              <div className="shop-modal-stat">
                <span className="shop-modal-stat-label">В лоте</span>
                <span className="shop-modal-stat-value">{formatKut(item.quantity)}</span>
              </div>
              <div className="shop-modal-stat">
                <span className="shop-modal-stat-label">Цена за шт</span>
                <span className="shop-modal-stat-value">{formatKut(price)}</span>
              </div>
              {!item.isMine ? (
                <div className="shop-modal-stat">
                  <span className="shop-modal-stat-label">Итого</span>
                  <span className="shop-modal-stat-value">{formatKut(totalCost)}</span>
                </div>
              ) : (
                <div className="shop-modal-stat">
                  <span className="shop-modal-stat-label">Вы получите</span>
                  <span className="shop-modal-stat-value">{formatKut(payoutIfSold)}</span>
                </div>
              )}
            </div>

            {item.isMine ? (
              <p className="market-modal-payout-hint">
                При продаже всего лота: {formatKut(grossIfSold)} КУТ − комиссия {commissionPercent}% ({formatKut(commissionIfSold)} КУТ)
              </p>
            ) : null}
          </div>

          <div className="shop-modal-actions">
            {item.isMine ? (
              <button
                type="button"
                className="farm-btn-danger shop-modal-confirm"
                disabled={isBusy}
                onClick={() => onCancelListing(item.id)}
              >
                {isBusy ? 'Снимаем…' : 'Снять с биржи'}
              </button>
            ) : (
              <>
                <button type="button" className="shop-modal-cancel" onClick={onClose}>
                  Отмена
                </button>
                <button
                  type="button"
                  className={`farm-btn-primary shop-modal-confirm ${needsTopUp ? 'shop-modal-confirm--donate' : ''}`}
                  disabled={confirmDisabled}
                  onClick={handleConfirmBuy}
                >
                  {confirmLabel}
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </Portal>
  )
}
