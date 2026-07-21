import { useEffect, useState } from 'react'
import Portal from './Portal'
import { fetchGiveaway } from '../lib/giveawaysClient'
import { RARITY_ACCENT, formatGiveawayDeadlineTime, formatGiveawayPrize } from '../constants/giveaways'
import { openTelegramBotLink, getTelegramUser } from '../lib/telegram'

const BOT_USERNAME = 'CuteGamingBot'

const CONDITION_LABEL = {
  balance: (cond) => `Баланс: ${cond.current} из ${cond.targetValue} КУТ`,
  harvest_count: (cond) => `Урожаев собрано: ${cond.current} из ${cond.targetValue}`,
  item_count: (cond) => `Предмет «${cond.itemId}»: ${cond.current} из ${cond.targetValue}`,
  channel_sub: (cond) => `Подписка на @${cond.itemId}`,
  referral_count: (cond) => `Приглашено друзей: ${cond.current} из ${cond.targetValue}`,
}

const CONDITION_NAV_TARGET = {
  balance: 'trade',
  harvest_count: 'farm',
  item_count: 'farm-inventory',
}

export default function GiveawayDetailModal({
  giveawayId,
  isOpen,
  onClose,
  onParticipate,
  onNavigateCondition,
  isParticipating,
  error,
}) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!isOpen || !giveawayId) {
      setDetail(null)
      return undefined
    }
    let cancelled = false
    setLoading(true)
    fetchGiveaway(giveawayId)
      .then((data) => {
        if (!cancelled) setDetail(data)
      })
      .catch(() => {
        if (!cancelled) setDetail(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [isOpen, giveawayId])

  if (!isOpen || !giveawayId) return null

  const accent = detail ? (RARITY_ACCENT[detail.rarity] ?? RARITY_ACCENT.common) : RARITY_ACCENT.common
  const isUpcoming = Boolean(detail?.startsAt) && new Date(detail.startsAt).getTime() > Date.now()

  return (
    <Portal lockScroll>
      <div className="shop-modal-root" role="presentation" onClick={onClose}>
        <div
          className="shop-modal giveaway-detail-modal"
          role="dialog"
          aria-modal="true"
          onClick={(e) => e.stopPropagation()}
          style={{ '--ticket-accent-strong': accent.strong, '--ticket-accent-glow': accent.glow }}
        >
          <button type="button" className="shop-modal-close" onClick={onClose} aria-label="Закрыть">✕</button>

          {loading || !detail ? (
            <p className="giveaway-detail-loading">Загрузка…</p>
          ) : (
            <>
              {/* Зона 1: приз + таймер */}
              <div className="giveaway-detail-hero">
                <div className="giveaway-detail-hero-icon-wrap">
                  <span className="giveaway-detail-hero-emoji" aria-hidden>
                    {detail.prize.type === 'kut' ? '💰' : (detail.prize.emoji ?? '🎁')}
                  </span>
                </div>
                <h2 className="giveaway-detail-title">{detail.title}</h2>
                <p className="giveaway-detail-prize">{formatGiveawayPrize(detail.prize)}</p>
                <span className="giveaway-detail-badge">
                  {detail.drawType === 'instant'
                    ? <>⚡ Мгновенно всем выполнившим</>
                    : detail.endsAt
                      ? <>🕒 {formatGiveawayDeadlineTime(detail.endsAt)}</>
                      : <>🕒 По таймеру</>}
                </span>
              </div>

              {/* Зона 2: условия */}
              <div className="giveaway-detail-conditions">
                {detail.conditions.length === 0 ? (
                  <p className="giveaway-detail-no-conditions">Условий нет — участвуйте сразу</p>
                ) : (
                  <div className="giveaway-detail-conditions-card">
                    {detail.conditions.map((cond, idx) => (
                      <div
                        key={idx}
                        className={`giveaway-detail-condition${cond.satisfied ? ' giveaway-detail-condition--done' : ''}`}
                      >
                        <span className="giveaway-detail-condition-status" aria-hidden>
                          {cond.satisfied ? '🟢' : '⚪'}
                        </span>
                        <span className="giveaway-detail-condition-label">
                          {(CONDITION_LABEL[cond.kind] ?? (() => cond.kind))(cond)}
                        </span>
                        {!cond.satisfied && cond.kind === 'channel_sub' && (
                          <button
                            type="button"
                            className="giveaway-detail-condition-goto"
                            onClick={() => openTelegramBotLink(`https://t.me/${cond.itemId}`)}
                          >
                            Перейти
                          </button>
                        )}
                        {!cond.satisfied && cond.kind === 'referral_count' && (
                          <button
                            type="button"
                            className="giveaway-detail-condition-goto"
                            onClick={() => {
                              const userId = getTelegramUser()?.id
                              if (!userId) return
                              const inviteLink = `https://t.me/${BOT_USERNAME}?start=${userId}`
                              openTelegramBotLink(`https://t.me/share/url?url=${encodeURIComponent(inviteLink)}`)
                            }}
                          >
                            Перейти
                          </button>
                        )}
                        {!cond.satisfied && cond.kind !== 'channel_sub' && cond.kind !== 'referral_count' && (
                          <button
                            type="button"
                            className="giveaway-detail-condition-goto"
                            onClick={() => onNavigateCondition(CONDITION_NAV_TARGET[cond.kind] ?? 'farm')}
                          >
                            Перейти
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Зона 3: действие */}
              {error && <p className="giveaway-detail-error">{error}</p>}
              {detail.result ? (
                <div className="giveaway-detail-result">
                  {detail.result.won
                    ? '🎉 Вы выиграли!'
                    : detail.winnerName
                      ? `🏆 Победитель: ${detail.winnerName}`
                      : detail.recipientsCount != null
                        ? `🎁 ${detail.recipientsCount} игроков получили приз`
                        : 'В этот раз не повезло'}
                </div>
              ) : detail.joined ? (
                <div className="giveaway-detail-joined">
                  {detail.drawType === 'instant' ? '✅ Приз получен' : '🎟️ Вы участвуете, ждите розыгрыша'}
                </div>
              ) : isUpcoming ? (
                <button type="button" className="giveaway-detail-cta" disabled>
                  ⏳ {formatGiveawayDeadlineTime(detail.startsAt)}
                </button>
              ) : (
                <button
                  type="button"
                  className={`giveaway-detail-cta${detail.conditionsMet ? ' giveaway-detail-cta--ready' : ''}`}
                  disabled={!detail.conditionsMet || isParticipating}
                  onClick={() => onParticipate(detail.id)}
                >
                  {isParticipating
                    ? 'Секунду…'
                    : detail.conditionsMet
                      ? 'Участвовать'
                      : <>🔒 Завершите задания</>}
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </Portal>
  )
}
