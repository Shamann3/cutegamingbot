import { useEscapeClose } from '../hooks/useEscapeClose'
import { formatKut } from '../utils/formatKut'
import { EMPTY_VALUE } from '../utils/displayText'
import {
  inventoryExchangeTotal,
  inventoryItemCardCells,
  inventoryMarketUnitPrice,
} from '../utils/inventoryEconomy'
import Portal from './Portal'

function totalFontSize(value) {
  const digits = String(Math.abs(value ?? 0)).length
  if (digits >= 8) return '1.15rem'
  if (digits >= 6) return '1.35rem'
  if (digits >= 5) return '1.55rem'
  return '1.75rem'
}

export default function InventoryItemModal({ item, isOpen, onClose }) {
  useEscapeClose(isOpen && Boolean(item), onClose)

  if (!isOpen || !item) return null

  const description = item.description?.trim()
  const totalValue = inventoryExchangeTotal(item)
  const marketUnit = inventoryMarketUnitPrice(item)
  const cells = inventoryItemCardCells(item)
  const showDesc = Boolean(description) && description !== item.meta?.trim()

  return (
    <Portal lockScroll>
      <div className="inv-card-root" role="presentation" onClick={onClose}>
        <div
          className="inv-card"
          role="dialog"
          aria-modal="true"
          aria-labelledby="inventory-item-title"
          onClick={(event) => event.stopPropagation()}
        >
          <button type="button" className="inv-card-close" onClick={onClose} aria-label="Закрыть">
            ✕
          </button>

          <div className="inv-card-body">
            <header className="inv-card-hero">
              <div className="inv-card-icon-ring" aria-hidden>
                <span className="inv-card-emoji">{item.emoji}</span>
              </div>

              <div className="inv-card-value-block">
                {totalValue != null ? (
                  <>
                    <p className="inv-card-total">
                      <span
                        className="inv-card-total-num"
                        style={{ fontSize: totalFontSize(totalValue) }}
                      >
                        {formatKut(totalValue)}
                      </span>
                      <span className="inv-card-total-currency">кут</span>
                    </p>
                    <p className="inv-card-total-hint">
                      Стоимость на бирже · {formatKut(item.count)} шт
                      {marketUnit ? ` × ${formatKut(marketUnit)}` : ''}
                    </p>
                  </>
                ) : (
                  <>
                    <p className="inv-card-total inv-card-total--empty">
                      <span className="inv-card-total-num">{EMPTY_VALUE}</span>
                    </p>
                    <p className="inv-card-total-hint">Нет данных о цене на бирже</p>
                  </>
                )}
              </div>

              <p className="inv-card-category">{item.groupLabel} · {item.categoryLabel}</p>
              <h2 id="inventory-item-title" className="inv-card-title">{item.name}</h2>
            </header>

            <div className="inv-card-grid" aria-label="Статистика предмета">
              {cells.map((cell) => (
                <div key={cell.id} className="inv-card-cell">
                  <span className="inv-card-cell-icon" aria-hidden>{cell.icon}</span>
                  <span className="inv-card-cell-label">{cell.label}</span>
                  <span className="inv-card-cell-value">{cell.value}</span>
                </div>
              ))}
            </div>

            {showDesc ? (
              <p className="inv-card-desc">{description}</p>
            ) : null}
          </div>

          <button type="button" className="farm-btn-primary inv-card-btn" onClick={onClose}>
            Понятно
          </button>
        </div>
      </div>
    </Portal>
  )
}
