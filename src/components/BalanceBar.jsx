import { useMemo } from 'react'
import StatChip from './StatChip'
import { buildBalanceBarChips } from '../utils/balanceBar'

export default function BalanceBar({
  balanceBar,
  kut,
  farmCrops = [],
  seedCounts = {},
  items = {},
  waterCount = 0,
  axe = null,
  fixed = false,
  anyPlotDry = false,
}) {
  const chips = useMemo(() => {
    if (balanceBar?.length) return balanceBar
    return buildBalanceBarChips({
      kut,
      farmCrops,
      seedCounts,
      items,
      waterCount,
      axe,
    })
  }, [balanceBar, kut, farmCrops, seedCounts, items, waterCount, axe])

  // В закреплённом режиме скрываем нулевые ресурсы они не нужны
  const visibleChips = fixed
    ? chips.filter((c) => c.kind === 'kut' || Number(c.value) > 0)
    : chips

  if (fixed) {
    const kinds = visibleChips.length
    return (
      <div className="farm-balance-bar--fixed farm-pantry" aria-label="Предметы фермы">
        <div className="farm-pantry-head">
          <span>Склад</span>
          <em>{kinds}</em>
        </div>
        <div className="farm-pantry-scroll" role="list">
          {visibleChips.map((chip, index) => {
            const isWaterWarn = anyPlotDry && (chip.kind === 'water')
            return (
              <StatChip
                key={`${chip.kind}-${chip.id}`}
                icon={chip.emoji}
                label={chip.label}
                value={chip.value}
                kind={isWaterWarn ? 'water-warn' : chip.kind}
                compact
                shelf
                enterIndex={index}
              />
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <div id="onboarding-balance" className="farm-balance-bar mb-4">
      <div className="farm-balance-bar-track" role="list" aria-label="Ресурсы фермы">
        {chips.map((chip) => (
          <StatChip
            key={`${chip.kind}-${chip.id}`}
            icon={chip.emoji}
            label={chip.label}
            value={chip.value}
            kind={chip.kind}
            muted={chip.kind !== 'kut' && Number(chip.value) === 0}
          />
        ))}
      </div>
    </div>
  )
}
