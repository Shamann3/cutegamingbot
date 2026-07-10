import { GrowthStage } from '../../utils/farmTiming'
import { PlotStatus } from '../../types/farm'

function SeedSprite() {
  return (
    <svg viewBox="0 0 32 32" className="w-10 h-10" aria-hidden>
      <rect x="14" y="20" width="4" height="4" fill="#5D4037" />
      <rect x="15" y="19" width="2" height="2" fill="#8D6E63" />
    </svg>
  )
}

function SproutSprite() {
  return (
    <svg viewBox="0 0 32 32" className="w-12 h-12" aria-hidden>
      <rect x="15" y="18" width="2" height="8" fill="#4CAF50" />
      <rect x="10" y="14" width="6" height="4" fill="#66BB6A" />
      <rect x="18" y="14" width="6" height="4" fill="#66BB6A" />
      <rect x="8"  y="16" width="4" height="3" fill="#81C784" />
      <rect x="20" y="16" width="4" height="3" fill="#81C784" />
    </svg>
  )
}

function BushSprite() {
  return (
    <svg viewBox="0 0 32 32" className="w-14 h-14" aria-hidden>
      <rect x="14" y="22" width="4" height="6" fill="#6D4C41" />
      <rect x="8"  y="12" width="16" height="12" fill="#43A047" />
      <rect x="6"  y="14" width="4"  height="8"  fill="#4CAF50" />
      <rect x="22" y="14" width="4"  height="8"  fill="#4CAF50" />
      <rect x="10" y="10" width="12" height="4"  fill="#66BB6A" />
      <rect x="12" y="8"  width="8"  height="4"  fill="#81C784" />
    </svg>
  )
}

function TreeSprite() {
  return (
    <svg viewBox="0 0 32 32" className="w-16 h-16" aria-hidden>
      <rect x="13" y="20" width="6"  height="10" fill="#5D4037" />
      <rect x="14" y="18" width="4"  height="3"  fill="#6D4C41" />
      <rect x="6"  y="8"  width="20" height="14" fill="#2E7D32" />
      <rect x="4"  y="10" width="6"  height="10" fill="#388E3C" />
      <rect x="22" y="10" width="6"  height="10" fill="#388E3C" />
      <rect x="8"  y="6"  width="16" height="6"  fill="#43A047" />
      <rect x="10" y="4"  width="12" height="4"  fill="#4CAF50" />
      <rect x="12" y="2"  width="8"  height="3"  fill="#66BB6A" />
    </svg>
  )
}

function TobaccoSproutSprite() {
  return (
    <svg viewBox="0 0 32 32" className="w-12 h-12" aria-hidden>
      <rect x="15" y="20" width="2" height="6" fill="#8D6E63" />
      <rect x="9"  y="14" width="8" height="5" fill="#7CB342" />
      <rect x="17" y="12" width="8" height="6" fill="#9CCC65" />
      <rect x="11" y="12" width="4" height="3" fill="#AED581" />
    </svg>
  )
}

function TobaccoBushSprite() {
  return (
    <svg viewBox="0 0 32 32" className="w-14 h-14" aria-hidden>
      <rect x="14" y="22" width="4"  height="6"  fill="#6D4C41" />
      <rect x="6"  y="10" width="10" height="12" fill="#689F38" />
      <rect x="16" y="8"  width="10" height="14" fill="#7CB342" />
      <rect x="10" y="8"  width="12" height="5"  fill="#9CCC65" />
      <rect x="18" y="6"  width="8"  height="4"  fill="#AED581" />
    </svg>
  )
}

function ReadyTobaccoSprite() {
  return (
    <svg viewBox="0 0 32 32" className="w-16 h-16 drop-shadow-md" aria-hidden>
      <rect x="14" y="22" width="4"  height="6"  fill="#5D4037" />
      <rect x="5"  y="8"  width="11" height="14" fill="#558B2F" />
      <rect x="16" y="6"  width="11" height="16" fill="#689F38" />
      <rect x="8"  y="6"  width="16" height="6"  fill="#7CB342" />
      <rect x="20" y="10" width="5"  height="8"  fill="#C5A572" className="animate-pulse-soft" />
      <rect x="7"  y="12" width="4"  height="7"  fill="#B8956A" />
    </svg>
  )
}

function WiltedSprite() {
  return (
    <svg viewBox="0 0 32 32" className="w-14 h-14" aria-hidden>
      <rect x="14" y="20" width="4"  height="8"  fill="#795548" />
      <rect x="6"  y="12" width="8"  height="6"  fill="#A1887F" transform="rotate(-25 10 15)" />
      <rect x="18" y="14" width="8"  height="6"  fill="#8D6E63" transform="rotate(20 22 17)"  />
      <rect x="10" y="10" width="6"  height="4"  fill="#BCAAA4" transform="rotate(-15 13 12)" />
    </svg>
  )
}

function ReadyTreeSprite() {
  return (
    <svg viewBox="0 0 32 32" className="w-16 h-16 drop-shadow-md" aria-hidden>
      <rect x="13" y="20" width="6"  height="10" fill="#5D4037" />
      <rect x="5"  y="6"  width="22" height="16" fill="#1B5E20" />
      <rect x="3"  y="8"  width="8"  height="12" fill="#2E7D32" />
      <rect x="23" y="8"  width="8"  height="12" fill="#2E7D32" />
      <rect x="7"  y="4"  width="18" height="6"  fill="#388E3C" />
      <rect x="9"  y="2"  width="14" height="4"  fill="#43A047" />
      <rect x="20" y="10" width="4"  height="4"  fill="#FFD54F" className="animate-pulse-soft" />
      <rect x="8"  y="12" width="3"  height="3"  fill="#FFCA28" />
    </svg>
  )
}

const TREE_STAGE_SPRITES = {
  [GrowthStage.SEED]:   SeedSprite,
  [GrowthStage.SPROUT]: SproutSprite,
  [GrowthStage.BUSH]:   BushSprite,
  [GrowthStage.TREE]:   TreeSprite,
}

const TOBACCO_STAGE_SPRITES = {
  [GrowthStage.SEED]:   SeedSprite,
  [GrowthStage.SPROUT]: TobaccoSproutSprite,
  [GrowthStage.BUSH]:   TobaccoBushSprite,
  [GrowthStage.TREE]:   TobaccoBushSprite,
}

export default function PlantSprite({ status, growthStage, cropKey = 'tree', className = '' }) {
  const isTobacco = cropKey === 'tobacco'
  const stageSprites = isTobacco ? TOBACCO_STAGE_SPRITES : TREE_STAGE_SPRITES

  if (status === PlotStatus.WITHERED)
    return <div className={`flex items-center justify-center ${className}`}><WiltedSprite /></div>

  if (status === PlotStatus.READY) {
    const R = isTobacco ? ReadyTobaccoSprite : ReadyTreeSprite
    return <div className={`flex items-center justify-center animate-float ${className}`}><R /></div>
  }

  if (status === PlotStatus.GROWING && growthStage) {
    const S = stageSprites[growthStage] ?? SproutSprite
    return <div className={`flex items-center justify-center animate-float ${className}`}><S /></div>
  }

  return null
}
