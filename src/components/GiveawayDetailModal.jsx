import { useCallback, useEffect, useState } from 'react'
import Portal from './Portal'
import { fetchGiveaway } from '../lib/giveawaysClient'
import { formatGiveawayDeadlineTime, formatGiveawayPrize } from '../constants/giveaways'
import { openTelegramBotLink, getTelegramUser } from '../lib/telegram'
import AnimatedPrizeIcon from './AnimatedPrizeIcon'
import UserNameLink from './UserNameLink'

const BOT_USERNAME = 'CuteGamingBot'

// Канал может прийти как @name, name или полный https://t.me/name — сводим
// к чистому имени, из которого строим и подпись, и ссылку «Перейти».
function channelStripped(raw) {
  return String(raw ?? '')
    .replace(/^https?:\/\/(t\.me|telegram\.me)\//i, '')
    .replace(/^@/, '')
    .replace(/\/+$/, '')
}
function channelHandle(raw) {
  return `@${channelStripped(raw)}`
}
function channelUrl(raw) {
  return `https://t.me/${channelStripped(raw)}`
}

// Короткая подпись условия + признак числового прогресса (для полоски).
const CONDITION_LABEL = {
  balance: () => 'Баланс КУТ',
  harvest_count: () => 'Урожаев собрано',
  item_count: (cond) => `Предмет «${cond.itemId}»`,
  channel_sub: (cond) => `Подписка на ${channelHandle(cond.itemId)}`,
  referral_count: () => 'Приглашено друзей',
}

const CONDITION_NAV_TARGET = {
  balance: 'trade',
  harvest_count: 'farm',
  item_count: 'farm-inventory',
}

// Иконка-квест для каждого типа условия.
const CONDITION_ICON = {
  balance: '💰',
  harvest_count: '🌾',
  item_count: '📦',
  channel_sub: '📣',
  referral_count: '🤝',
}

function pluralPlayers(n) {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return 'игрок'
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return 'игрока'
  return 'игроков'
}

function prizeWithIcon(prize) {
  return `${prize?.type === 'kut' ? '💰 ' : ''}${formatGiveawayPrize(prize)}`
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

  const reload = useCallback((withSpinner = true) => {
    if (!giveawayId) return
    if (withSpinner) setLoading(true)
    fetchGiveaway(giveawayId)
      .then((data) => setDetail(data))
      .catch(() => { if (withSpinner) setDetail(null) })
      .finally(() => setLoading(false))
  }, [giveawayId])

  useEffect(() => {
    if (!isOpen || !giveawayId) {
      setDetail(null)
      return undefined
    }
    reload()
    return undefined
  }, [isOpen, giveawayId, reload])

  // Перепроверка условий после возврата из Telegram: игрок нажал «Перейти»,
  // подписался на канал и вернулся в мини-апп — при возврате фокуса тихо
  // перезапрашиваем детали (channel_sub проверяется живьём, force_refresh),
  // и выполненное условие сразу становится зелёным. Без спиннера, чтобы не
  // моргать, если ничего не изменилось.
  useEffect(() => {
    if (!isOpen || !giveawayId) return undefined
    const onVisible = () => {
      if (document.visibilityState === 'visible') reload(false)
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [isOpen, giveawayId, reload])

  if (!isOpen || !giveawayId) return null

  // Окно розыгрыша всегда носит фирменную розово-золотую тему вкладки (не по
  // редкости) — иначе common/rare красили бы рамку в зелёный/синий. Редкость
  // читается на карточках-билетах в списке. --tab-accent-muted задаём здесь,
  // т.к. модалка рендерится через Portal вне обёртки .tab-theme-giveaways.
  const themeVars = {
    '--ticket-accent-strong': '#f472b6',
    '--ticket-accent-glow': 'rgba(244, 114, 182, 0.34)',
    '--tab-accent-muted': 'rgba(249, 168, 212, 0.72)',
  }
  const isUpcoming = Boolean(detail?.startsAt) && new Date(detail.startsAt).getTime() > Date.now()
  const totalConditions = detail ? detail.conditions.length : 0
  const satisfiedCount = detail ? detail.conditions.filter((c) => c.satisfied).length : 0
  const progressPercent = totalConditions > 0
    ? Math.round((satisfiedCount / totalConditions) * 100)
    : 0

  return (
    <Portal lockScroll>
      <div className="shop-modal-root" role="presentation" onClick={onClose}>
        <div
          className="shop-modal giveaway-detail-modal"
          role="dialog"
          aria-modal="true"
          onClick={(e) => e.stopPropagation()}
          style={themeVars}
        >
          <button type="button" className="shop-modal-close" onClick={onClose} aria-label="Закрыть">✕</button>

          {loading || !detail ? (
            <p className="giveaway-detail-loading">Загрузка…</p>
          ) : (
            <>
              {/* Лента-серийник */}
              <div className="giveaway-detail-ribbon">
                <span className="giveaway-detail-ribbon-serial">
                  БИЛЕТ № {String(detail.id).padStart(4, '0')}
                </span>
                <span className="giveaway-detail-ribbon-label">
                  {detail.result ? 'Итоги' : detail.drawType === 'instant' ? 'Мгновенный' : 'Розыгрыш'}
                </span>
              </div>

              {/* Зона 1: приз + таймер */}
              <div className="giveaway-detail-hero">
                <div className="giveaway-detail-hero-icon-wrap">
                  <span className="giveaway-detail-hero-ring" aria-hidden />
                  <span className="giveaway-detail-hero-seal" aria-hidden />
                  <AnimatedPrizeIcon
                    emoji={detail.prize.type === 'kut' ? '💰' : (detail.prize.emoji ?? '🎁')}
                    animation={detail.prize.animation}
                    iconClassName="giveaway-detail-hero-emoji"
                    mediaClassName="giveaway-detail-hero-emoji giveaway-detail-hero-media"
                  />
                </div>
                <h2 className="giveaway-detail-title">{detail.title}</h2>
                <p className="giveaway-detail-prize">{formatGiveawayPrize(detail.prize)}</p>
                {!detail.result && (
                  <span className="giveaway-detail-badge">
                    {detail.drawType === 'instant'
                      ? <>⚡ Мгновенно всем выполнившим</>
                      : detail.endsAt
                        ? <>🕒 {formatGiveawayDeadlineTime(detail.endsAt)}</>
                        : <>🕒 По таймеру</>}
                  </span>
                )}
              </div>

              <div className="giveaway-detail-perf" aria-hidden />

              {detail.result ? (
                /* Завершён — раскрытие победителя */
                detail.result.won ? (
                  <div className="giveaway-winner giveaway-winner--you">
                    <div className="giveaway-winner-inner">
                      <div className="giveaway-winner-crown" aria-hidden>🎉</div>
                      <p className="giveaway-winner-eyebrow">Поздравляем</p>
                      <p className="giveaway-winner-name">Вы выиграли!</p>
                      <span className="giveaway-winner-prize">{prizeWithIcon(detail.prize)}</span>
                    </div>
                  </div>
                ) : detail.winnerName ? (
                  <div className="giveaway-winner">
                    <div className="giveaway-winner-inner">
                      <div className="giveaway-winner-crown" aria-hidden>👑</div>
                      <p className="giveaway-winner-eyebrow">Победитель</p>
                      <p className="giveaway-winner-name">
                        <UserNameLink
                          userId={detail.winnerUserId || detail.winnerId}
                          name={detail.winnerName}
                        />
                      </p>
                      <div className="giveaway-winner-laurel" aria-hidden>
                        <span className="giveaway-winner-laurel-line" />
                        <span>🌿</span>
                        <span className="giveaway-winner-laurel-line giveaway-winner-laurel-line--right" />
                      </div>
                      <span className="giveaway-winner-prize">{prizeWithIcon(detail.prize)}</span>
                    </div>
                  </div>
                ) : detail.recipientsCount != null ? (
                  <div className="giveaway-winner">
                    <div className="giveaway-winner-inner">
                      <div className="giveaway-winner-crown" aria-hidden>🎁</div>
                      <p className="giveaway-winner-eyebrow">Приз получили</p>
                      <p className="giveaway-winner-name">
                        {detail.recipientsCount} {pluralPlayers(detail.recipientsCount)}
                      </p>
                      <span className="giveaway-winner-prize">{prizeWithIcon(detail.prize)}</span>
                    </div>
                  </div>
                ) : (
                  <div className="giveaway-winner">
                    <div className="giveaway-winner-inner">
                      <div className="giveaway-winner-crown" aria-hidden>🎲</div>
                      <p className="giveaway-winner-eyebrow">Розыгрыш завершён</p>
                      <p className="giveaway-winner-name" style={{ fontSize: '1.3rem' }}>В этот раз не повезло</p>
                    </div>
                  </div>
                )
              ) : (
                <>
                  {/* Прогресс выполнения условий */}
                  {totalConditions > 0 && (
                    <div className="giveaway-progress">
                      <div className="giveaway-progress-top">
                        <span className="giveaway-progress-label">
                          Выполнено {satisfiedCount} из {totalConditions} условий
                        </span>
                        <span className="giveaway-progress-percent">{progressPercent}%</span>
                      </div>
                      <div className="giveaway-progress-bar">
                        <span
                          className="giveaway-progress-bar-fill"
                          style={{ width: `${progressPercent}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Зона 2: список квестов-условий */}
                  <div className="giveaway-detail-conditions">
                    {detail.conditions.length === 0 ? (
                      <p className="giveaway-detail-no-conditions">Условий нет — участвуйте сразу</p>
                    ) : (
                      <div className="giveaway-ledger">
                        <div className="giveaway-ledger-head">
                          <span className="giveaway-ledger-head-title">Задания</span>
                          <span className="giveaway-ledger-head-count">
                            {satisfiedCount} / {detail.conditions.length}
                          </span>
                        </div>
                        {detail.conditions.map((cond, idx) => {
                          const hasProgress = cond.kind !== 'channel_sub'
                            && cond.targetValue != null && cond.current != null
                          const percent = hasProgress && cond.targetValue > 0
                            ? Math.min(100, Math.round((cond.current / cond.targetValue) * 100))
                            : (cond.satisfied ? 100 : 0)
                          const label = (CONDITION_LABEL[cond.kind] ?? (() => cond.kind))(cond)
                          return (
                            <div
                              key={idx}
                              className={`giveaway-detail-condition${cond.satisfied ? ' giveaway-detail-condition--done' : ''}`}
                            >
                              <span className="giveaway-detail-condition-status" aria-hidden>
                                {cond.satisfied ? '✓' : (CONDITION_ICON[cond.kind] ?? '○')}
                              </span>
                              <div className="giveaway-detail-condition-main">
                                <span className="giveaway-detail-condition-label">{label}</span>
                                {hasProgress && (
                                  <div className="giveaway-detail-condition-progress">
                                    <span className="giveaway-detail-condition-bar">
                                      <span
                                        className="giveaway-detail-condition-bar-fill"
                                        style={{ width: `${percent}%` }}
                                      />
                                    </span>
                                    <span className="giveaway-detail-condition-num">
                                      {cond.current} / {cond.targetValue}
                                    </span>
                                  </div>
                                )}
                              </div>
                              {!cond.satisfied && cond.kind === 'channel_sub' && (
                                <button
                                  type="button"
                                  className="giveaway-detail-condition-goto"
                                  onClick={() => openTelegramBotLink(channelUrl(cond.itemId))}
                                >
                                  Открыть
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
                                  Позвать
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
                          )
                        })}
                      </div>
                    )}
                  </div>

                  {/* Зона 3: действие */}
                  {error && <p className="giveaway-detail-error">{error}</p>}

                  {!detail.joined
                    && Array.isArray(detail.participantsPreview)
                    && detail.participantsPreview.length > 0 && (
                    <p className="giveaway-participants-preview">
                      Участники:{' '}
                      {detail.participantsPreview.map((p, idx) => (
                        <span key={p.userId || idx}>
                          {idx > 0 ? ', ' : ''}
                          <UserNameLink userId={p.userId} name={p.name} />
                        </span>
                      ))}
                      {(detail.participantsCount || 0) > detail.participantsPreview.length ? '…' : ''}
                    </p>
                  )}

                  {detail.joined ? (
                    detail.drawType === 'instant' ? (
                      <div className="giveaway-detail-joined">✅ Приз получен</div>
                    ) : (
                      <div className="giveaway-participating">
                        <p className="giveaway-participating-title">🎉 Вы участвуете в розыгрыше</p>
                        <div className="giveaway-participating-stats">
                          <span className="giveaway-participating-stat">
                            👥 {detail.participantsCount ?? 0} {pluralPlayers(detail.participantsCount ?? 0)}
                          </span>
                          {(detail.participantsCount ?? 0) > 0 && (
                            <span className="giveaway-participating-stat giveaway-participating-chance">
                              🎯 шанс ~1 из {detail.participantsCount}
                            </span>
                          )}
                        </div>
                        {Array.isArray(detail.participantsPreview) && detail.participantsPreview.length > 0 && (
                          <p className="giveaway-participants-preview">
                            Недавно:{' '}
                            {detail.participantsPreview.map((p, idx) => (
                              <span key={p.userId || idx}>
                                {idx > 0 ? ', ' : ''}
                                <UserNameLink userId={p.userId} name={p.name} />
                              </span>
                            ))}
                          </p>
                        )}
                      </div>
                    )
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
            </>
          )}
        </div>
      </div>
    </Portal>
  )
}
