import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../lib/apiClient'
import { fetchPlayerProfile, telegramProfileUrl } from '../lib/profileClient'
import { openTelegramBotLink } from '../lib/telegram'
import { useEscapeClose } from '../hooks/useEscapeClose'
import { EMPTY_VALUE } from '../utils/displayText'
import Portal from './Portal'

function formatCount(value) {
  const n = Number(value) || 0
  return new Intl.NumberFormat('ru-RU').format(n)
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

function StatCard({ emoji, label, value, accent = 'gold' }) {
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
  const nextRankText = rank?.nextAt
    ? `До следующего ранга: ${formatCount(rank.nextAt - (profile?.salesCount ?? 0))} продаж`
    : 'Максимальный ранг на бирже'
  const canOpenTg = Boolean(tgUrl) && !profile?.isSelf

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
                      {formatCount(profile?.salesCount ?? 0)} продаж
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

                <div className="player-profile-stats-grid">
                  <StatCard
                    emoji="🤝"
                    label="Сделок"
                    value={formatCount(profile?.salesCount ?? 0)}
                    accent="green"
                  />
                  <StatCard
                    emoji="📦"
                    label="Предметов продано"
                    value={formatCount(profile?.itemsSold ?? 0)}
                    accent="gold"
                  />
                  <StatCard
                    emoji="🏷️"
                    label="Лотов сейчас"
                    value={formatCount(profile?.activeListings ?? 0)}
                    accent="sky"
                  />
                  <StatCard
                    emoji="⭐"
                    label="Ранг"
                    value={rank?.label ?? EMPTY_VALUE}
                    accent="violet"
                  />
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
