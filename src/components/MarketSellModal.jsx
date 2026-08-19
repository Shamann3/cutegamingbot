import { useEffect, useMemo, useState } from 'react'
import { formatKut } from '../utils/formatKut'
import { calcMarketCommission, calcMarketSellerPayout } from '../lib/marketClient'
import { useEscapeClose, useEnterConfirm } from '../hooks/useEscapeClose'
import Portal from './Portal'

export default function MarketSellModal({
  items,
  isOpen,
  isLoading,
  isBusy,
  error,
  commissionPercent = 7,
  onClose,
  onConfirm,
  onRetry,
}) {
  const [selectedId, setSelectedId] = useState('')
  const [quantityText, setQuantityText] = useState('1')
  const [priceText, setPriceText] = useState('10')

  // Сбрасываем форму при открытии
  useEffect(() => {
    if (!isOpen) return
    setSelectedId('')
    setQuantityText('1')
    setPriceText('10')
  }, [isOpen])

  // Отбираем только предметы с положительным количеством
  const availableItems = useMemo(
    () => items.filter((item) => item.count > 0),
    [items]
  )

  // Если выбранный предмет пропал из доступных — выбираем первый доступный
  useEffect(() => {
    if (availableItems.length === 0) {
      if (selectedId !== '') setSelectedId('')
      return
    }
    const exists = availableItems.some((item) => item.itemId === selectedId)
    if (!exists) {
      setSelectedId(availableItems[0].itemId)
    }
  }, [availableItems, selectedId])

  const selected =
    availableItems.find((item) => item.itemId === selectedId) ??
    availableItems[0] ??
    null
  const maxQty = selected ? Math.min(selected.count, 99) : 0

  // Ограничиваем количество при ручном вводе и при изменении предмета
  useEffect(() => {
    const n = Number.parseInt(quantityText, 10)
    if (maxQty > 0 && Number.isFinite(n) && n > maxQty) {
      setQuantityText(String(maxQty))
    }
  }, [selectedId, maxQty])

  const parsedQty = Number.parseInt(quantityText, 10)
  const parsedPrice = Number.parseInt(priceText, 10)
  const hasValidQty = Number.isFinite(parsedQty) && parsedQty >= 1
  const hasValidPrice = Number.isFinite(parsedPrice) && parsedPrice >= 1
  const quantity = hasValidQty ? Math.min(parsedQty, maxQty) : 1
  const price = hasValidPrice ? Math.min(parsedPrice, 999_999) : 1
  const grossTotal = price * quantity
  const commission = calcMarketCommission(grossTotal, commissionPercent)
  const sellerPayout = calcMarketSellerPayout(grossTotal, commissionPercent)

  const canSubmit =
    Boolean(selected) &&
    maxQty > 0 &&
    !isBusy &&
    !isLoading &&
    hasValidQty &&
    hasValidPrice

  useEnterConfirm(
    isOpen,
    () => {
      if (canSubmit && selected) onConfirm(selected.itemId, price, quantity)
    },
    { enabled: !isBusy }
  )

  if (!isOpen) return null

  return (
    <Portal lockScroll>
      <div className="shop-modal-root" role="presentation" onClick={onClose}>
        <div
          className="shop-modal market-sell-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="market-sell-title"
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

          <div className="shop-modal-content market-sell-content">
            <h2 id="market-sell-title" className="shop-modal-title">
              Выставить на биржу
            </h2>
            <p className="market-sell-hint">
              Вы можете выставить любые предметы из рюкзака, включая саженцы и воду.
              Комиссия биржи {commissionPercent}% удерживается при продаже.
            </p>

            {isLoading ? (
              <p className="market-sell-empty">Загрузка рюкзака…</p>
            ) : error ? (
              <div className="market-sell-error">
                <p className="market-sell-empty">{error}</p>
                {onRetry ? (
                  <button
                    type="button"
                    className="farm-btn-primary market-sell-retry"
                    onClick={onRetry}
                  >
                    Повторить
                  </button>
                ) : null}
              </div>
            ) : availableItems.length === 0 ? (
              <p className="market-sell-empty">Нет предметов для продажи</p>
            ) : (
              <>
                <label className="market-sell-field">
                  <span>Предмет</span>
                  <select
                    className="market-sell-select"
                    value={selected?.itemId ?? ''}
                    onChange={(e) => setSelectedId(e.target.value)}
                  >
                    {availableItems.map((item) => (
                      <option key={item.itemId} value={item.itemId}>
                        {item.emoji} {item.name} ({item.count} шт)
                      </option>
                    ))}
                  </select>
                </label>

                <label className="market-sell-field">
                  <span>
                    Количество{' '}
                    <span className="market-sell-field-max">
                      макс {formatKut(maxQty)} шт
                    </span>
                  </span>
                  <input
                    type="text"
                    inputMode="numeric"
                    className={`market-sell-input${
                      Number.parseInt(quantityText, 10) > maxQty
                        ? ' market-sell-input--over'
                        : ''
                    }`}
                    value={quantityText}
                    onChange={(e) => {
                      const raw = e.target.value.replace(/\D/g, '')
                      if (raw === '') {
                        setQuantityText('')
                        return
                      }
                      const n = Math.min(Number.parseInt(raw, 10), maxQty)
                      setQuantityText(String(n))
                    }}
                  />
                </label>

                <label className="market-sell-field">
                  <span>Цена за 1 шт (КУТ)</span>
                  <input
                    type="text"
                    inputMode="numeric"
                    className="market-sell-input"
                    value={priceText}
                    onChange={(e) => {
                      const raw = e.target.value.replace(/\D/g, '')
                      if (raw === '') {
                        setPriceText('')
                        return
                      }
                      const n = Math.min(Number.parseInt(raw, 10), 999_999)
                      setPriceText(String(n))
                    }}
                  />
                </label>

                <div className="market-sell-breakdown">
                  <div className="market-sell-breakdown-row">
                    <span>Сумма сделки</span>
                    <strong>{formatKut(grossTotal)} КУТ</strong>
                  </div>
                  <div className="market-sell-breakdown-row market-sell-breakdown-fee">
                    <span>Комиссия биржи ({commissionPercent}%)</span>
                    <strong>−{formatKut(commission)} КУТ</strong>
                  </div>
                  <div className="market-sell-breakdown-row market-sell-breakdown-total">
                    <span>Вы получите</span>
                    <strong>{formatKut(sellerPayout)} КУТ</strong>
                  </div>
                </div>
              </>
            )}
          </div>

          <div className="shop-modal-actions">
            <button
              type="button"
              className="shop-modal-cancel"
              onClick={onClose}
            >
              Отмена
            </button>
            <button
              type="button"
              className="farm-btn-primary shop-modal-confirm"
              disabled={!canSubmit}
              onClick={() =>
                selected && onConfirm(selected.itemId, price, quantity)
              }
            >
              {isBusy ? 'Выставляем…' : 'Выставить'}
            </button>
          </div>
        </div>
      </div>
    </Portal>
  )
}