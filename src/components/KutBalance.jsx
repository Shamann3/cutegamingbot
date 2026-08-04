import { formatKut } from '../utils/formatKut'

function balanceAmountStyle(formatted) {
  const len = formatted.length
  if (len >= 12) return { fontSize: '0.78rem' }
  if (len >= 10) return { fontSize: '0.88rem' }
  if (len >= 8) return { fontSize: '0.98rem' }
  return undefined
}

/**
 * iOS-toolbar: баланс слева, действие «Пополнить» справа (trailing).
 */
export default function KutBalance({ value, className = '', onDonate }) {
  const formatted = formatKut(value)
  const amountStyle = balanceAmountStyle(formatted)
  const withDonate = typeof onDonate === 'function'

  return (
    <div
      className={[
        'kut-balance-wrap',
        withDonate ? 'kut-balance-wrap--toolbar' : '',
        className,
      ].filter(Boolean).join(' ')}
    >
      <div
        className="kut-balance-bar"
        aria-label={`Баланс ${formatted} КУТ`}
      >
        <div className="kut-balance-main">
          <span className="kut-balance-coin" aria-hidden>💰</span>
          <div className="kut-balance-copy">
            <span className="kut-balance-eyebrow">Баланс</span>
            <div className="kut-balance-value-row">
              <span className="kut-balance-amount" style={amountStyle}>{formatted}</span>
              <span className="kut-balance-unit">КУТ</span>
            </div>
          </div>
        </div>

        {withDonate ? (
          <button
            type="button"
            className="kut-topup-btn"
            onClick={onDonate}
            aria-label="Пополнить баланс"
          >
            <span className="kut-topup-plus" aria-hidden>+</span>
            <span className="kut-topup-label">Пополнить</span>
          </button>
        ) : null}
      </div>
    </div>
  )
}
