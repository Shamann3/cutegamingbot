import { useEffect, useState } from 'react'
import { formatKut } from '../utils/formatKut'
import { itemBuyPrice } from '../lib/shopClient'
import { useEscapeClose, useEnterConfirm } from '../hooks/useEscapeClose'
import ContextualDonatePrompt from './ContextualDonatePrompt'
import { buildDonateContext, suggestDonateAmount } from '../utils/contextualDonate'
import Portal from './Portal'

export default function ShopPurchaseModal({
  item,
  kut,
  couponCount = 0,
  couponDiscount = null,
  isOpen,
  isBuying,
  onClose,
  onConfirm,
  onContextualDonate,
}) {
  const [quantityText, setQuantityText] = useState('1')
  const [useCoupon, setUseCoupon] = useState(false)

  useEffect(() => {
    setQuantityText('1')
    setUseCoupon(false)
  }, [item?.id])

  useEscapeClose(isOpen && Boolean(item), onClose, { enabled: !isBuying })

  const price = item ? itemBuyPrice(item) : 0
  const maxByStock = item ? Math.max(0, item.remains ?? 0) : 0
  const maxQty = Math.min(maxByStock, 99)

  const parsedQuantity = Number.parseInt(quantityText, 10)
  const hasValidQuantity = Number.isFinite(parsedQuantity) && parsedQuantity >= 1
  const quantity = hasValidQuantity ? Math.min(parsedQuantity, maxQty) : 1

  const totalCost = price * (hasValidQuantity ? quantity : 0)
  const isCouponItself = item?.name === 'Купон на скидку'
  const canUseCoupon = couponCount > 0 && !isCouponItself
  const couponActive = canUseCoupon && useCoupon

  const couponMin = couponDiscount?.minPercent ?? 20
  const couponMax = couponDiscount?.maxPercent ?? 75
  const couponUnits = couponDiscount?.units ?? 1
  // Точный процент выпадает на сервере и до успешной покупки не показывается.
  // Нижнюю границу цены (макс. скидка на couponUnits шт.) считаем только чтобы
  // не дать начать покупку, которой не хватит кут даже в лучшем случае.
  // Купон списывается только после успешной оплаты.
  const couponUnitCount = Math.min(quantity, couponUnits)
  const bestCaseCost = hasValidQuantity
    ? price * (quantity - couponUnitCount)
      + (price - Math.round((price * couponMax) / 100)) * couponUnitCount
    : 0
  const canAfford = couponActive ? kut >= bestCaseCost : kut >= totalCost
  const outOfStock = !item || maxByStock < 1
  const needsTopUp = !outOfStock && hasValidQuantity && !canAfford
  const hasSale = item?.salePrice != null && item.salePrice > 0
  const neededCost = couponActive ? bestCaseCost : totalCost

  const confirmDisabled = isBuying || outOfStock
    || (!needsTopUp && !canAfford)
    || !hasValidQuantity || quantity < 1

  const actionLabel = item ? `Купить «${item.name}»` : 'Покупка'
  const suggestedTopUp = needsTopUp ? suggestDonateAmount(kut, neededCost) : 0

  let confirmLabel = 'Подтвердить покупку'
  if (isBuying) confirmLabel = 'Оформляем покупку…'
  else if (outOfStock) confirmLabel = 'Нет в наличии'
  else if (needsTopUp) confirmLabel = `Пополнить ${formatKut(suggestedTopUp)} КУТ`
  else if (couponActive) confirmLabel = 'Купить со скидкой 🎟'

  // Хук ДО раннего return иначе нарушение Rules of Hooks
  useEnterConfirm(isOpen && Boolean(item) && !confirmDisabled, () => {
    if (needsTopUp && onContextualDonate) {
      onContextualDonate(buildDonateContext({ balance: kut, neededCost, actionLabel }))
    } else if (!confirmDisabled) {
      onConfirm(item.id, quantity, couponActive)
    }
  }, { enabled: !isBuying })

  if (!isOpen || !item) return null

  const setQuantityValue = (next) => {
    const clamped = Math.max(1, Math.min(next, maxQty))
    setQuantityText(String(clamped))
  }

  const handleQuantityInput = (event) => {
    const raw = event.target.value
    if (raw === '') {
      setQuantityText('')
      return
    }

    const digitsOnly = raw.replace(/\D/g, '')
    if (digitsOnly === '') {
      setQuantityText('')
      return
    }

    const next = Number.parseInt(digitsOnly, 10)
    if (!Number.isFinite(next)) return
    setQuantityText(String(Math.min(next, maxQty)))
  }

  const handleQuantityBlur = () => {
    const next = Number.parseInt(quantityText, 10)
    if (!Number.isFinite(next) || next < 1) {
      setQuantityText('1')
      return
    }
    setQuantityText(String(Math.min(next, maxQty)))
  }

  const handleConfirm = () => {
    if (needsTopUp && onContextualDonate) {
      onContextualDonate(buildDonateContext({ balance: kut, neededCost, actionLabel }))
      return
    }
    if (confirmDisabled) return
    onConfirm(item.id, quantity, couponActive)
  }

  return (
    <Portal lockScroll>
      <div className="shop-modal-root" role="presentation" onClick={onClose}>
      <div
        className="shop-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shop-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          className="shop-modal-close"
          onClick={onClose}
          aria-label="Закрыть"
        >
          ✕
        </button>

        <div className="shop-modal-hero">
          <span className="shop-modal-emoji" aria-hidden>{item.emoji}</span>
        </div>

        <div className="shop-modal-content">
          <p className="shop-modal-category">{item.categoryLabel}</p>
          <h2 id="shop-modal-title" className="shop-modal-title">{item.name}</h2>
          {item.bio || item.description ? (
            <div className="shop-modal-bio">
              <p className="shop-modal-bio-label">О предмете</p>
              <p className="shop-modal-description">{item.bio || item.description}</p>
            </div>
          ) : null}
          {item.composition && Object.keys(item.composition).length > 0 ? (
            <ul className="shop-modal-composition">
              {Object.entries(item.composition).map(([name, count]) => (
                <li key={name}>
                  <span>{name}</span>
                  <span>×{count}</span>
                </li>
              ))}
            </ul>
          ) : null}

          <div className="shop-modal-quantity">
            <div className="shop-modal-quantity-head">
              <span className="shop-modal-quantity-label">Количество к покупке</span>
              <span className="shop-modal-quantity-limit">
                доступно: {formatKut(maxQty)}
              </span>
            </div>
            <div className="shop-modal-quantity-stepper">
              <button
                type="button"
                className="shop-modal-qty-step"
                onClick={() => setQuantityValue(quantity - 1)}
                disabled={!hasValidQuantity || quantity <= 1}
                aria-label="Меньше"
              >
                −
              </button>
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                className="shop-modal-qty-input"
                value={quantityText}
                onChange={handleQuantityInput}
                onBlur={handleQuantityBlur}
                aria-label="Количество"
              />
              <button
                type="button"
                className="shop-modal-qty-step"
                onClick={() => setQuantityValue(quantity + 1)}
                disabled={!hasValidQuantity || quantity >= maxQty}
                aria-label="Больше"
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

          {canUseCoupon ? (
            <div className={`shop-modal-coupon-wrap${couponActive ? ' shop-modal-coupon-wrap--active' : ''}`}>
              <button
                type="button"
                className={`shop-modal-coupon${couponActive ? ' shop-modal-coupon--active' : ''}`}
                onClick={() => setUseCoupon((prev) => !prev)}
                aria-pressed={couponActive}
              >
                <span className="shop-modal-coupon-icon" aria-hidden>🎟</span>
                <span className="shop-modal-coupon-copy">
                  <span className="shop-modal-coupon-title">Купон на скидку</span>
                  <span className="shop-modal-coupon-desc">
                    {couponActive
                      ? `Скидка ${couponMin}–${couponMax}% на ${couponUnits} шт. выпадет только после покупки`
                      : `У вас: ${couponCount} шт. Включите, чтобы купить со скидкой`}
                  </span>
                </span>
                <span className="shop-modal-coupon-switch" aria-hidden>
                  <span className="shop-modal-coupon-switch-thumb" />
                </span>
              </button>
              {couponActive ? (
                <p className="shop-modal-coupon-warn" role="note">
                  Купон спишется только после успешной покупки.
                  Точный процент скидки заранее не показывается — вы узнаете его
                  в чеке после оплаты. Отмена или ошибка покупки купон не тратит.
                </p>
              ) : null}
            </div>
          ) : null}

          {needsTopUp ? (
            <ContextualDonatePrompt
              balance={kut}
              neededCost={totalCost}
              actionLabel={actionLabel}
              onDonate={onContextualDonate}
            />
          ) : null}

          <div className="shop-modal-stats">
            <div className="shop-modal-stat">
              <span className="shop-modal-stat-label">В наличии</span>
              <span className="shop-modal-stat-value">{formatKut(item.remains)}</span>
            </div>
            <div className="shop-modal-stat">
              <span className="shop-modal-stat-label">Цена</span>
              <span className="shop-modal-stat-value shop-modal-price">
                {hasSale ? (
                  <span className="shop-modal-price-stack">
                    <span className="shop-modal-price-old">{formatKut(item.price)}</span>
                    <span className="shop-modal-price-main">{formatKut(price)}</span>
                  </span>
                ) : (
                  <span>{formatKut(price)}</span>
                )}
              </span>
            </div>
            <div className="shop-modal-stat">
              <span className="shop-modal-stat-label">Итого</span>
              <span className="shop-modal-stat-value">
                {couponActive ? (
                  <span className="shop-modal-coupon-total">
                    <span className="shop-modal-price-old">{formatKut(totalCost)}</span>
                    <span className="shop-modal-coupon-total-hint">
                      до −{couponMax}% 🎟
                    </span>
                  </span>
                ) : (
                  formatKut(totalCost)
                )}
              </span>
            </div>
          </div>
        </div>

        <div className="shop-modal-actions">
          <button type="button" className="shop-modal-cancel" onClick={onClose}>
            Отмена
          </button>
          <button
            type="button"
            className={`farm-btn-primary shop-modal-confirm ${needsTopUp ? 'shop-modal-confirm--donate' : ''}`}
            disabled={confirmDisabled}
            onClick={handleConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
    </Portal>
  )
}
