import FarmBackground from './FarmBackground'
import TabAtmosphere from './TabAtmosphere'
import VineFrame from './VineFrame'
import '../styles/giveaways.css'

export default function GiveawaysModule({ isActive = true }) {
  return (
    <div className="relative min-h-screen tab-theme-giveaways giveaways-module" aria-hidden={!isActive}>
      <FarmBackground />
      <TabAtmosphere variant="giveaways" />

      <div className="relative z-10 giveaways-shell py-4 pb-2 animate-slide-up">
        <header className="giveaways-header">
          <p className="giveaways-header-eyebrow">Cute</p>
          <h1 className="giveaways-header-title">Розыгрыши</h1>
        </header>

        <VineFrame className="giveaways-frame">
          <div className="giveaways-empty">
            <span className="giveaways-empty-icon" aria-hidden>🎁</span>
            <p>Скоро здесь появятся розыгрыши призов</p>
          </div>
        </VineFrame>
      </div>
    </div>
  )
}
