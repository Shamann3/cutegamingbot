import { formatKut } from '../utils/formatKut'

function balanceAmountStyle(formatted) {
  const len = formatted.length
  if (len >= 12) return { fontSize: '0.72rem' }
  if (len >= 10) return { fontSize: '0.82rem' }
  if (len >= 8) return { fontSize: '0.92rem' }
  return undefined
}

export default function KutBalance({ value, className = '', onDonate }) {
  const formatted = formatKut(value)
  const amountStyle = balanceAmountStyle(formatted)

  return (
    <div className={`kut-balance-wrap ${className}`.trim()}>
      <div
        className="kut-balance"
        aria-label={`Баланс ${formatted} КУТ`}
      >
        <div className="kut-balance-frame">
          <div className="kut-balance-inner">
            <span className="kut-balance-coin" aria-hidden>💰</span>
            <div className="kut-balance-copy">
              <span className="kut-balance-eyebrow">Баланс</span>
              <span className="kut-balance-amount" style={amountStyle}>{formatted}</span>
            </div>
            <div className="kut-balance-side">
              <span className="kut-balance-unit">КУТ</span>
            </div>
          </div>
        </div>
      </div>
      {onDonate ? (
        <button type="button" className="kut-donate-btn" onClick={onDonate}>
          <span className="kut-donate-btn-shine" aria-hidden />
          <span className="kut-donate-btn-frame">
            <span className="kut-donate-btn-icon" aria-hidden>⭐</span>
            <span className="kut-donate-btn-label">
              <span className="kut-donate-btn-label-line">Пополнить</span>
              <span className="kut-donate-btn-label-line">баланс</span>
            </span>
          </span>
        </button>
      ) : null}
    </div>
  )
}
