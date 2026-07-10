import {
  DONATE_DEFAULT_AMOUNT,
  DONATE_MAX_AMOUNT,
  DONATE_MIN_AMOUNT,
  DONATE_PRESETS,
} from '../constants/donate'

/** Сколько КУТ не хватает для покупки. */
export function calcShortfall(balance, neededCost) {
  const bal = Math.max(0, Number(balance) || 0)
  const cost = Math.max(0, Number(neededCost) || 0)
  return Math.max(0, cost - bal)
}

/** Минимальная сумма пополнения, чтобы хватило на покупку (с запасом по пресетам). */
export function suggestDonateAmount(balance, neededCost) {
  const shortfall = calcShortfall(balance, neededCost)
  if (shortfall <= 0) return DONATE_DEFAULT_AMOUNT

  for (const preset of DONATE_PRESETS) {
    if (preset >= shortfall) return preset
  }

  return Math.min(DONATE_MAX_AMOUNT, Math.max(DONATE_MIN_AMOUNT, shortfall))
}

export function buildDonateContext({ balance, neededCost, actionLabel }) {
  const shortfall = calcShortfall(balance, neededCost)
  return {
    balance: Math.max(0, Number(balance) || 0),
    neededCost: Math.max(0, Number(neededCost) || 0),
    shortfall,
    actionLabel: actionLabel?.trim() || null,
    suggestedAmount: suggestDonateAmount(balance, neededCost),
  }
}
