import { useMemo, useState } from 'react'
import FarmBackground from './FarmBackground'
import TabAtmosphere from './TabAtmosphere'
import GiveawayTicketCard from './GiveawayTicketCard'
import GiveawayDetailModal from './GiveawayDetailModal'
import GiveawayHistoryCard from './GiveawayHistoryCard'
import { useGiveaways } from '../hooks/useGiveaways'
import { useGiveawayHistory } from '../hooks/useGiveawayHistory'
import { RARITY_ORDER } from '../constants/giveaways'
import '../styles/giveaways.css'

const TABS = [
  { id: 'active', label: '🟢 Активные' },
  { id: 'upcoming', label: '⌛ Скоро' },
  { id: 'past', label: '🏆 Прошедшие' },
]

function sortByRarity(list) {
  return [...list].sort((a, b) => RARITY_ORDER.indexOf(b.rarity) - RARITY_ORDER.indexOf(a.rarity))
}

export default function GiveawaysModule({ isActive = true, onNavigateCondition }) {
  const { giveaways, initialLoading, error, participate, participatingId, clearError } = useGiveaways({ isActive })
  const history = useGiveawayHistory()
  const [openId, setOpenId] = useState(null)
  const [tab, setTab] = useState('active')

  const handleOpenDetail = (id) => {
    clearError()
    setOpenId(id)
  }

  const handleNavigateCondition = (target) => {
    setOpenId(null)
    onNavigateCondition?.(target)
  }

  const handleTabChange = (id) => {
    setTab(id)
    if (id === 'past' && history.giveaways === null) history.load()
  }

  const now = Date.now()
  // status === 'active' здесь не избыточно: get_giveaways_state отдаёт и уже
  // завершённые (status='completed') розыгрыши тоже — чтобы игрок успел
  // увидеть «вы выиграли»/«завершён» в статус-лейбле карточки на один
  // цикл поллинга. Теперь у завершённых есть отдельный дом (вкладка
  // «Прошедшие», через useGiveawayHistory) — здесь их явно исключаем, иначе
  // они годами копились бы в «Активных».
  const activeList = useMemo(
    () => sortByRarity(giveaways.filter((g) => (
      g.status === 'active' && (!g.startsAt || new Date(g.startsAt).getTime() <= now)
    ))),
    [giveaways, now],
  )
  const upcomingList = useMemo(
    () => sortByRarity(giveaways.filter((g) => (
      g.status === 'active' && g.startsAt && new Date(g.startsAt).getTime() > now
    ))),
    [giveaways, now],
  )

  return (
    <div className="relative min-h-screen tab-theme-giveaways giveaways-module" aria-hidden={!isActive}>
      <FarmBackground />
      <TabAtmosphere variant="giveaways" />

      <div className="relative z-10 giveaways-shell py-4 pb-2 animate-slide-up">
        <header className="giveaways-header">
          <p className="giveaways-header-eyebrow">Cute</p>
          <h1 className="giveaways-header-title">Розыгрыши</h1>
        </header>

        <div className="segment-tabs" role="tablist" aria-label="Разделы розыгрышей">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              className={`segment-tab${tab === t.id ? ' segment-tab-active' : ''}`}
              onClick={() => handleTabChange(t.id)}
            >
              {t.label}{t.id === 'active' ? ` (${activeList.length})` : ''}
            </button>
          ))}
        </div>

        {error && <p className="giveaways-empty">{error}</p>}

        {tab !== 'past' && initialLoading ? (
          <p className="giveaways-empty">Загрузка…</p>
        ) : tab === 'active' ? (
          activeList.length === 0 ? (
            <div className="giveaways-empty">
              <span className="giveaways-empty-icon" aria-hidden>🎁</span>
              <p>Скоро здесь появятся розыгрыши призов</p>
            </div>
          ) : (
            <div className="giveaways-ticket-grid">
              {activeList.map((giveaway) => (
                <GiveawayTicketCard
                  key={giveaway.id}
                  giveaway={giveaway}
                  onOpenDetail={handleOpenDetail}
                  onSwipeParticipate={participate}
                />
              ))}
            </div>
          )
        ) : tab === 'upcoming' ? (
          upcomingList.length === 0 ? (
            <div className="giveaways-empty">
              <span className="giveaways-empty-icon" aria-hidden>⌛</span>
              <p>Анонсов пока нет — загляните позже</p>
            </div>
          ) : (
            <div className="giveaways-ticket-grid">
              {upcomingList.map((giveaway) => (
                <GiveawayTicketCard
                  key={giveaway.id}
                  giveaway={giveaway}
                  onOpenDetail={handleOpenDetail}
                  onSwipeParticipate={participate}
                />
              ))}
            </div>
          )
        ) : history.loading || history.giveaways === null ? (
          <p className="giveaways-empty">Загрузка…</p>
        ) : history.giveaways.length === 0 ? (
          <div className="giveaways-empty">
            <span className="giveaways-empty-icon" aria-hidden>🏆</span>
            <p>Прошедших розыгрышей пока не было</p>
          </div>
        ) : (
          <div className="giveaways-history-list">
            {history.giveaways.map((giveaway) => (
              <GiveawayHistoryCard key={giveaway.id} giveaway={giveaway} />
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
        error={openId ? error : null}
      />
    </div>
  )
}
