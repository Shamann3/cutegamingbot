import { plotBuyPrice } from '../types/farm'

/**
 * Только купленные грядки + одна карточка «купить следующую» (без лимита и закрытых слотов).
 */
export function buildFarmSlots({ plots, ownedPlots, maxPlots, nextPlotPrice }) {
  const slots = []

  for (let id = 1; id <= ownedPlots; id += 1) {
    const plot = plots.find((p) => p.id === id)
    slots.push({ type: 'plot', plot: plot ?? { id, status: 'EMPTY' } })
  }

  if (ownedPlots < maxPlots) {
    slots.push({
      type: 'buy',
      price: nextPlotPrice ?? plotBuyPrice(ownedPlots + 1),
    })
  }

  return slots
}
