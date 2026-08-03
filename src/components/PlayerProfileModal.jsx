import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../lib/apiClient'
import { fetchPlayerProfile, telegramProfileUrl } from '../lib/profileClient'
import { openTelegramBotLink } from '../lib/telegram'
import { useEscapeClose } from '../hooks/useEscapeClose'
import { EMPTY_VALUE } from '../utils/displayText'
import Portal from './Portal'
import UserNameLink from './UserNameLink'

function formatCount(value) {
  const n = Number(value) || 0
  return new Intl.NumberFormat('ru-RU').format(n)
}

function formatRegDate(iso) {
  if (!iso) return null
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return null
    return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
  } catch {
    return null
  }
}

function ProfileAvatar({ photoUrl, displayName, rank }) {
  const initial = (displayName || '?').trim().charAt(0).toUpperCase() || '?'
  return (
    <div className="player-profile-avatar-wrap">
      <div className="player-profile-avatar-ring" aria-hidden />
      {photoUrl ? (
        <img
          src={photoUrl}
          alt=""
          className="player-profile-avatar player-profile-avatar-img"
        />
      ) : (
        <span className="player-profile-avatar" aria-hidden>
          {initial}
        </span>
      )}
      {rank ? (
        <span className="player-profile-rank-chip" title={rank.label}>
          <span aria-hidden>{rank.emoji}</span>
          <span>{rank.label}</span>
        </span>
      ) : null}
    </div>
  )
}

function StatCard({ emoji, label, value, accent = 'green' }) {
  return (
    <div className={`player-profile-stat-card player-profile-stat-card--${accent}`}>
      <span className="player-profile-stat-emoji" aria-hidden>{emoji}</span>
      <div className="player-profile-stat-copy">
        <span className="player-profile-stat-value">{value}</span>
        <span className="player-profile-stat-label">{label}</span>
      </div>
    </div>
  )
}

function MetaRow({ label, value }) {
  if (value == null || value === '' || value === EMPTY_VALUE) return null
  return (
    <div className="player-profile-meta-row">
      <span className="player-profile-meta-label">{label}</span>
      <strong className="player-profile-meta-value">{value}</strong>
    </div>
  )
}

export default function PlayerProfileModal({ userId, isOpen, onClose }) {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEscapeClose(isOpen, onClose, { enabled: !loading })

  const loadProfile = useCallback(async () => {
    if (!userId) return
    setLoading(true)
    setError(null)
    try {
      const data = await fetchPlayerProfile(userId)
      setProfile(data)
    } catch (err) {
      setProfile(null)
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить профиль')
    } finally {
      setLoading(false)
    }
  }, [userId])

  useEffect(() => {
    if (!isOpen || !userId) return undefined
    loadProfile()
    return undefined
  }, [isOpen, userId, loadProfile])

  useEffect(() => {
    if (!isOpen) {
      setProfile(null)
      setError(null)
    }
  }, [isOpen])

  if (!isOpen || !userId) return null

  const tgUrl = telegramProfileUrl(profile?.username, profile?.userId || userId)
  const rank = profile?.sellerRank
  const progressPct = Math.round((rank?.progress ?? 0) * 100)
  const sales = profile?.salesCount ?? profile?.marketSalesCount ?? 0
  const nextRankText = rank?.nextAt
    ? `До следующего ранга: ${formatCount(rank.nextAt - sales)} продаж`
    : 'Максимальный ранг на бирже'
  const canOpenTg = Boolean(tgUrl) && !profile?.isSelf
  const regDate = formatRegDate(profile?.registeredAt)
  const referer = profile?.refererName
  const refererId = profile?.refererUserId

  return (
    <Portal lockScroll>
      <div className="shop-modal-root player-profile-root" role="presentation" onClick={onClose}>
        <div
          className="shop-modal player-profile-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="player-profile-title"
          onClick={(event) => event.stopPropagation()}
        >
          <button type="button" className="shop-modal-close player-profile-close" onClick={onClose} aria-label="Закрыть">
            ✕
          </button>

          <div className="player-profile-header">
            <div className="player-profile-header-glow" aria-hidden />
            <p className="player-profile-header-eyebrow">Профиль игрока</p>
          </div>

          <div className="player-profile-hero">
            {loading ? (
              <div className="player-profile-avatar-wrap">
                <span className="player-profile-avatar player-profile-avatar-loading" aria-hidden />
              </div>
            ) : (
              <ProfileAvatar
                photoUrl={profile?.photoUrl}
                displayName={profile?.displayName}
                rank={rank}
              />
            )}
          </div>

          <div className="shop-modal-content player-profile-content">
            {loading ? (
              <p className="player-profile-status">Загружаем карточку игрока…</p>
            ) : error ? (
              <p className="player-profile-status player-profile-status-error" role="alert">{error}</p>
            ) : (
              <>
                <h2 id="player-profile-title" className="player-profile-name">
                  {profile?.displayName}
                </h2>

                {profile?.isSelf ? (
                  <p className="player-profile-self-badge">Ваш профиль</p>
                ) : null}

                {profile?.username ? (
                  <button
                    type="button"
                    className="player-profile-username"
                    onClick={() => tgUrl && openTelegramBotLink(tgUrl)}
                  >
                    @{profile.username}
                  </button>
                ) : (
                  <p className="player-profile-id">ID {profile?.userId}</p>
                )}

                <div className="player-profile-rank-panel">
                  <div className="player-profile-rank-top">
                    <span className="player-profile-rank-title">
                      {rank?.emoji} {rank?.label}
                    </span>
                    <span className="player-profile-rank-count">
                      {formatCount(sales)} продаж
                    </span>
                  </div>
                  <div className="player-profile-rank-bar" aria-hidden>
                    <span
                      className="player-profile-rank-bar-fill"
                      style={{ width: `${progressPct}%` }}
                    />
                  </div>
                  <p className="player-profile-rank-hint">{nextRankText}</p>
                </div>

                {(profile?.countryEmoji || profile?.daysInGame > 0 || regDate) && (
                  <p className="player-profile-meta">
                    {profile?.countryEmoji ? `${profile.countryEmoji} ` : ''}
                    {profile?.daysInGame > 0
                      ? `${formatCount(profile.daysInGame)} дн. в игре`
                      : 'Новый игрок'}
                    {regDate ? ` · с ${regDate}` : ''}
                  </p>
                )}

                <div className="player-profile-stats-grid">
                  <StatCard
                    emoji="💰"
                    label="Баланс"
                    value={`${formatCount(profile?.balance ?? 0)} КУТ`}
                    accent="green"
                  />
                  <StatCard
                    emoji="⭐"
                    label="Опыт"
                    value={formatCount(profile?.experience ?? 0)}
                    accent="violet"
                  />
                  <StatCard
                    emoji="🌾"
                    label="Урожаи"
                    value={formatCount(profile?.harvestCount ?? 0)}
                    accent="green"
                  />
                  <StatCard
                    emoji="🔨"
                    label="Крафт"
                    value={formatCount(profile?.craftCount ?? 0)}
                    accent="sky"
                  />
                  <StatCard
                    emoji="🤝"
                    label="Сделок"
                    value={formatCount(sales)}
                    accent="gold"
                  />
                  <StatCard
                    emoji="📦"
                    label="Продано"
                    value={formatCount(profile?.itemsSold ?? profile?.marketItemsSold ?? 0)}
                    accent="gold"
                  />
                  <StatCard
                    emoji="🏷️"
                    label="Лотов"
                    value={formatCount(profile?.activeListings ?? 0)}
                    accent="violet"
                  />
                  <StatCard
                    emoji="👥"
                    label="Рефералы"
                    value={formatCount(profile?.referrals ?? 0)}
                    accent="sky"
                  />
                </div>

                <div className="player-profile-extra">
                  <MetaRow
                    label="Игры"
                    value={`${formatCount(profile?.wins ?? 0)} / ${formatCount(profile?.losses ?? 0)}`}
                  />
                  {(profile?.winAmount ?? 0) > 0 && (
                    <MetaRow label="Выиграно" value={`${formatCount(profile.winAmount)} КУТ`} />
                  )}
                  <MetaRow
                    label="Репутация"
                    value={`+${formatCount(profile?.repPlus ?? 0)} / −${formatCount(profile?.repMinus ?? 0)}`}
                  />
                  {referer && (
                    <div className="player-profile-meta-row">
                      <span className="player-profile-meta-label">Пригласил</span>
                      <strong className="player-profile-meta-value">
                        {refererId ? (
                          <UserNameLink userId={refererId} name={referer} />
                        ) : (
                          referer
                        )}
                      </strong>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>

          <div className="shop-modal-actions player-profile-actions">
            {canOpenTg ? (
              <button
                type="button"
                className="farm-btn-primary shop-modal-confirm player-profile-tg-btn"
                onClick={() => openTelegramBotLink(tgUrl)}
              >
                Открыть в Telegram
              </button>
            ) : null}
            <button type="button" className="shop-modal-cancel" onClick={onClose}>
              Закрыть
            </button>
          </div>
        </div>
      </div>
    </Portal>
  )
}
