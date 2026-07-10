import { useState } from 'react'

export default function FarmDailySeedPanel({  seedEconomy,
  farmCrops,
  claiming,
  onClaim,
}) {
  const [seedChoice, setSeedChoice] = useState(null)

  if (!seedEconomy) return null

  const plantableCrops = (farmCrops ?? []).filter((crop) => crop.seedId)
  const selectedSeedId = seedChoice ?? plantableCrops[0]?.seedId ?? null
  const selectedCrop = plantableCrops.find((crop) => crop.seedId === selectedSeedId)
  const amount = seedEconomy.dailySeedAmount ?? 1
  const dropPercent = seedEconomy.harvestDropPercent ?? 25

  if (seedEconomy.dailySeedClaimedToday) {
    return (
      <div className="farm-daily-seed farm-daily-seed--claimed" role="status">
        <span className="farm-daily-seed-icon" aria-hidden>✅</span>
        <div className="farm-daily-seed-copy">
          <p className="farm-daily-seed-title">Бесплатное семя получено</p>
          <p className="farm-daily-seed-sub">
            Завтра снова можно забрать {amount} семечко в заданиях. С урожая ещё шанс {dropPercent}% 🌱
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="farm-daily-seed">
      <div className="farm-daily-seed-head">
        <span className="farm-daily-seed-icon" aria-hidden>🎁</span>
        <div className="farm-daily-seed-copy">
          <p className="farm-daily-seed-title">Ежедневное семя</p>
          <p className="farm-daily-seed-sub">
            Семена: ценный ресурс. Не выпало с урожая ({dropPercent}%)? Забери {amount} бесплатно.
          </p>
        </div>
      </div>

      {plantableCrops.length > 1 ? (
        <div className="farm-daily-seed-choices" role="group" aria-label="Выбор семян">
          {plantableCrops.map((crop) => (
            <button
              key={crop.seedId}
              type="button"
              className={`farm-daily-seed-choice ${selectedSeedId === crop.seedId ? 'farm-daily-seed-choice--active' : ''}`}
              onClick={() => setSeedChoice(crop.seedId)}
              disabled={claiming}
            >
              <span aria-hidden>{crop.seedEmoji ?? '🌱'}</span>
              {crop.seedName ?? crop.displayName}
            </button>
          ))}
        </div>
      ) : null}

      <button
        type="button"
        className="farm-daily-seed-btn"
        disabled={claiming || !selectedSeedId}
        onClick={() => onClaim?.(selectedSeedId)}
      >
        {claiming
          ? 'Выдаём…'
          : `Получить ${selectedCrop?.seedEmoji ?? '🌱'} ${amount} семечко`}
      </button>
    </div>
  )
}
