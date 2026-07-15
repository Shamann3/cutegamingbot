import { useEffect, useState } from 'react'
import FarmBackground from './FarmBackground'
import TabAtmosphere from './TabAtmosphere'
import VineFrame from './VineFrame'
import KutBalance from './KutBalance'
import { fetchMyProfile } from '../lib/profileClient'
import { fetchCollection } from '../lib/chestClient'
import { useEquippedCosmetics } from '../hooks/useEquippedCosmetics'
import { RARITY_ACCENT } from '../constants/chests'
import '../styles/chests.css'
import '../styles/cosmetic-effects.css'

const BOARDS = [
  { id: 'balance', label: 'Баланс', emoji: '💰', unit: 'кут' },
  { id: 'harvests', label: 'Урожай', emoji: '🌾', unit: 'сборов' },
  { id: 'sales', label: 'Биржа', emoji: '💱', unit: 'предметов' },
]

function Avatar({ photoUrl, name, size = 56 }) {
  const [err, setErr] = useState(false)
  const letter = (name || '?')[0].toUpperCase()
  if (photoUrl && !err) {
    return (
      <img
        src={photoUrl}
        alt={name}
        className="profile-avatar-img"
        style={{ width: size, height: size, borderRadius: '50%', objectFit: 'cover' }}
        onError={() => setErr(true)}
      />
    )
  }
  return (
    <div className="profile-avatar-fallback" style={{ width: size, height: size, fontSize: size * 0.4 }}>
      {letter}
    </div>
  )
}

function StatCard({ emoji, label, value, sub }) {
  return (
    <div className="profile-stat-card">
      <span className="profile-stat-emoji">{emoji}</span>
      <span className="profile-stat-value">{value?.toLocaleString('ru-RU') ?? '-'}</span>
      <span className="profile-stat-label">{label}</span>
      {sub && <span className="profile-stat-sub">{sub}</span>}
    </div>
  )
}

function LeaderRow({ item, valueLabel }) {
  const medals = ['🥇', '🥈', '🥉']
  const medal = medals[item.rank - 1]
  return (
    <div className={`profile-leader-row ${item.isMe ? 'profile-leader-row--me' : ''}`}>
      <span className="profile-leader-rank">
        {medal ?? <span className="profile-leader-rank-num">{item.rank}</span>}
      </span>
      <Avatar photoUrl={item.photoUrl} name={item.name} size={32} />
      <span className="profile-leader-name">{item.name}</span>
      <span className="profile-leader-value">{item.value?.toLocaleString('ru-RU')} {valueLabel}</span>
    </div>
  )
}

export default function ProfileModule({ isActive = true }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [board, setBoard] = useState('balance')
  const [showcase, setShowcase] = useState([])
  const { equipped } = useEquippedCosmetics()

  useEffect(() => {
    if (!isActive) return
    setLoading(true)
    fetchMyProfile()
      .then(setData)
      .catch((e) => setError(e?.message || 'Ошибка загрузки'))
      .finally(() => setLoading(false))
  }, [isActive])

  useEffect(() => {
    if (!isActive) return
    fetchCollection()
      .then((c) => {
        const equipped = [...c.sets.flatMap((s) => s.items), ...c.loose].filter((i) => i.equipped)
        setShowcase(equipped.slice(0, 3))
      })
      .catch(() => {})
  }, [isActive])

  const profile = data?.profile
  const leaderboard = data?.leaderboard ?? {}
  const activeBoard = BOARDS.find((b) => b.id === board) ?? BOARDS[0]
  const rows = leaderboard[board] ?? []
  const total = leaderboard.total ?? 0
  const myRank = leaderboard.myRank?.[board] ?? 0
  const myValue = leaderboard.myValue?.[board] ?? 0
  const iMeInTop = rows.some((r) => r.isMe)

  return (
    <div className="relative min-h-screen tab-theme-profile profile-module">
      <FarmBackground />
      <TabAtmosphere variant="profile" />

      <div className="relative z-10 profile-shell animate-slide-up">
        <header className="profile-module-header">
          <div className="profile-module-header-main">
            <p className="profile-module-eyebrow">Игрок · статистика</p>
            <h1 className="profile-module-title">
              <span aria-hidden>👤</span> Профиль
            </h1>
          </div>
          {profile && <KutBalance value={profile.balance} className="profile-module-balance" />}
        </header>

        {loading && (
          <div className="profile-loading">Загрузка профиля…</div>
        )}

        {error && !loading && (
          <div className="profile-error">{error}</div>
        )}

        {!loading && profile && (
          <>
            {/* Карточка игрока */}
            <VineFrame className="profile-card-frame">
              <div className="profile-card">
                <div className="profile-avatar-wrap">
                  <Avatar photoUrl={profile.photoUrl} name={profile.displayName} size={64} />
                  {equipped.frame && (
                    <span className="profile-frame-badge" aria-hidden>{equipped.frame.emoji}</span>
                  )}
                </div>
                <div className="profile-card-info">
                  <p className="profile-card-name">{profile.displayName}</p>
                  {profile.username && (
                    <p className="profile-card-username">@{profile.username}</p>
                  )}
                  <p className="profile-card-days">
                    В игре {profile.daysInGame === 0 ? 'менее дня' : `${profile.daysInGame} ${pluralDays(profile.daysInGame)}`}
                  </p>
                  {equipped.title && (
                    <div className="profile-title-emblem">
                      <span className="profile-title-seal">{equipped.title.emoji}</span>
                      <span className="profile-title-name">{equipped.title.name}</span>
                    </div>
                  )}
                </div>
              </div>
            </VineFrame>

            {/* Витрина косметики */}
            {showcase.length > 0 && (
              <div className="profile-showcase">
                <div className="profile-showcase-label">Витрина</div>
                <div className="profile-showcase-row">
                  {showcase.map((i) => (
                    <div key={i.cosmeticId} className="profile-showcase-slot" style={{ '--rar': RARITY_ACCENT[i.rarity] }}>
                      <span className="profile-showcase-glyph">{i.emoji}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Статистика */}
            <div className="profile-stats-grid">
              <StatCard emoji="🌾" label="Урожаев" value={profile.harvestCount} />
              <StatCard emoji="⚗️" label="Крафтов" value={profile.craftCount} />
              <StatCard emoji="💱" label="Продано" value={profile.marketItemsSold} sub="предметов" />
              <StatCard emoji="🏪" label="Сделок" value={profile.marketSalesCount} sub="на бирже" />
            </div>

            {/* Лидерборд */}
            <VineFrame className="profile-leaderboard-frame">
              <section className="profile-leaderboard">
                <header className="profile-leaderboard-header farm-panel-header">
                  <span aria-hidden>🏆</span>
                  <h2 className="text-sm font-extrabold tracking-tight text-amber-50">Топ игроков</h2>
                </header>

                {/* Переключатель */}
                <div className="profile-board-tabs">
                  {BOARDS.map((b) => (
                    <button
                      key={b.id}
                      type="button"
                      className={`profile-board-tab ${board === b.id ? 'profile-board-tab--active' : ''}`}
                      onClick={() => setBoard(b.id)}
                    >
                      {b.emoji} {b.label}
                    </button>
                  ))}
                </div>

                {/* Список */}
                <div className="profile-leader-list">
                  {rows.length === 0 ? (
                    <p className="profile-leader-empty">Пока нет данных</p>
                  ) : (
                    <>
                      {rows.map((item) => (
                        <LeaderRow key={item.userId} item={item} valueLabel={activeBoard.unit} />
                      ))}

                      {/* Моя позиция если не в топ-10 */}
                      {!iMeInTop && myRank > 0 && (
                        <>
                          <div className="profile-leader-gap">
                            <span>···</span>
                          </div>
                          <div className="profile-leader-row profile-leader-row--me">
                            <span className="profile-leader-rank">
                              <span className="profile-leader-rank-num">{myRank}</span>
                            </span>
                            <Avatar photoUrl={profile?.photoUrl} name={profile?.displayName} size={32} />
                            <span className="profile-leader-name">{profile?.displayName} <span className="profile-leader-you">ты</span></span>
                            <span className="profile-leader-value">{myValue?.toLocaleString('ru-RU')} {activeBoard.unit}</span>
                          </div>
                          {total > 0 && (
                            <p className="profile-leader-total">из {total.toLocaleString('ru-RU')} игроков</p>
                          )}
                        </>
                      )}
                    </>
                  )}
                </div>
              </section>
            </VineFrame>
          </>
        )}
      </div>
    </div>
  )
}

function pluralDays(n) {
  if (n % 10 === 1 && n % 100 !== 11) return 'день'
  if (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20)) return 'дня'
  return 'дней'
}
