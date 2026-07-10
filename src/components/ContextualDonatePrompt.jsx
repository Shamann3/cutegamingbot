import { formatKut } from '../utils/formatKut'
import { calcShortfall, suggestDonateAmount } from '../utils/contextualDonate'

export default function ContextualDonatePrompt({
  balance,
  neededCost,
  actionLabel,
  onDonate,
  className = '',
}) {
  const shortfall = calcShortfall(balance, neededCost)
  if (shortfall <= 0) return null

  const suggested = suggestDonateAmount(balance, neededCost)

  return (
    <div className={`contextual-donate-prompt ${className}`.trim()} role="status">
      <div className="contextual-donate-prompt-copy">
        <p className="contextual-donate-prompt-title">
          Не хватает <strong>{formatKut(shortfall)} КУТ</strong>
        </p>
        <p className="contextual-donate-prompt-sub">
          {actionLabel
            ? `${actionLabel}: нужно ${formatKut(neededCost)} КУТ, у вас ${formatKut(balance)}`
            : `Нужно ${formatKut(neededCost)} КУТ, у вас ${formatKut(balance)}`}
        </p>
      </div>
      <button
        type="button"
        className="contextual-donate-prompt-btn"
        onClick={() => onDonate?.({ balance, neededCost, actionLabel })}
      >
        <span aria-hidden>⭐</span>
        Пополнить {formatKut(suggested)} КУТ
      </button>
    </div>
  )
}
