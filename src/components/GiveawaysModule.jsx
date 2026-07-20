import { useState } from 'react'
import FarmBackground from './FarmBackground'
import TabAtmosphere from './TabAtmosphere'
import GiveawayTicketCard from './GiveawayTicketCard'
import GiveawayDetailModal from './GiveawayDetailModal'
import { useGiveaways } from '../hooks/useGiveaways'
import '../styles/giveaways.css'

export default function GiveawaysModule({ isActive = true, onNavigateCondition }) {
  const { giveaways, initialLoading, error, participate, participatingId } = useGiveaways({ isActive })
  const [openId, setOpenId] = useState(null)

  const handleNavigateCondition = (target) => {
    setOpenId(null)
    onNavigateCondition?.(target)
  }

  return (
    <div className="relative min-h-screen tab-theme-giveaways giveaways-module" aria-hidden={!isActive}>
      <FarmBackground />
      <TabAtmosphere variant="giveaways" />

      <div className="relative z-10 giveaways-shell py-4 pb-2 animate-slide-up">
        <header className="giveaways-header">
          <p className="giveaways-header-eyebrow">Cute</p>
          <h1 className="giveaways-header-title">Розыгрыши</h1>
        </header>

        {error && <p className="giveaways-empty">{error}</p>}

        {initialLoading ? (
          <p className="giveaways-empty">Загрузка…</p>
        ) : giveaways.length === 0 ? (
          <div className="giveaways-empty">
            <span className="giveaways-empty-icon" aria-hidden>🎁</span>
            <p>Скоро здесь появятся розыгрыши призов</p>
          </div>
        ) : (
          <div className="giveaways-ticket-grid">
            {giveaways.map((giveaway) => (
              <GiveawayTicketCard
                key={giveaway.id}
                giveaway={giveaway}
                onOpenDetail={setOpenId}
                onSwipeParticipate={participate}
              />
            ))}
          </div>
        )}
      </div>

      <GiveawayDetailModal
        giveawayId={openId}
        isOpen={Boolean(openId)}
        onClose={() => setOpenId(null)}
        onParticipate={async (id) => {
          const ok = await participate(id)
          if (ok) setOpenId(null)
        }}
        onNavigateCondition={handleNavigateCondition}
        isParticipating={participatingId === openId}
      />
    </div>
  )
}
