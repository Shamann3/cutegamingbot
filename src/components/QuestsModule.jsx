import { useEffect, useMemo, useRef, useState } from 'react'
import FarmBackground from './FarmBackground'
import TabAtmosphere from './TabAtmosphere'
import VineFrame from './VineFrame'
import KutBalance from './KutBalance'
import DonateModal from './DonateModal'
import { useQuests } from '../hooks/useQuests'
import { useContextualDonate } from '../hooks/useContextualDonate'

const PERIOD_ORDER = ['hourly', 'daily', 'weekly', 'events']
const PERIOD_ICONS = {
  hourly: '⏱',
  daily: '📅',
  weekly: '🗓',
  events: '🎉',
}

function errorClass(code) {
  if (code === 'auth') return 'quests-toast-auth'
  if (code === 'rate_limit') return 'quests-toast-rate'
  if (code === 'maintenance') return 'quests-toast-maint'
  return 'quests-toast-error'
}

function rewardLabel(rewards) {
  if (!rewards?.length) return 'Семя в инвентарь'
  return rewards.map((item) => {
    if (item.kind === 'kut') return `+${item.amount} КУТ`
    if (item.label) return item.label
    return `+${item.amount}`
  }).join(' · ')
}

function formatRemaining(totalSec) {
  const sec = Math.max(0, Number(totalSec) || 0)
  if (sec >= 86400) {
    const days = Math.floor(sec / 86400)
    const hours = Math.floor((sec % 86400) / 3600)
    return hours > 0 ? `${days}д ${hours}ч` : `${days}д`
  }
  if (sec >= 3600) {
    const hours = Math.floor(sec / 3600)
    const minutes = Math.floor((sec % 3600) / 60)
    return minutes > 0 ? `${hours}ч ${minutes}м` : `${hours}ч`
  }
  const minutes = Math.floor(sec / 60)
  const seconds = sec % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

function useServerRemainingTimer(initialRemainingSec) {
  const initialRef = useRef(initialRemainingSec)
  const startedAtRef = useRef(performance.now())

  const [remaining, setRemaining] = useState(() => {
    if (initialRemainingSec == null) return null
    return Math.max(0, Number(initialRemainingSec) || 0)
  })

  useEffect(() => {
    if (initialRemainingSec == null) {
      setRemaining(null)
      return undefined
    }

    initialRef.current = initialRemainingSec
    startedAtRef.current = performance.now()
    const initial = Math.max(0, Number(initialRemainingSec) || 0)

    setRemaining(initial)

    const tick = () => {
      const elapsed = Math.floor((performance.now() - startedAtRef.current) / 1000)
      setRemaining(Math.max(0, initialRef.current - elapsed))
    }

    const timer = window.setInterval(tick, 1000)
    return () => window.clearInterval(timer)
  }, [initialRemainingSec])

  return remaining
}

function QuestTimerChip({ remainingSec, onExpire }) {
  const remaining = useServerRemainingTimer(remainingSec)
  const expiredRef = useRef(false)

  useEffect(() => {
    expiredRef.current = false
  }, [remainingSec])

  useEffect(() => {
    if (remaining === 0 && !expiredRef.current) {
      expiredRef.current = true
      onExpire?.()
    }
  }, [onExpire, remaining])

  const display = remaining != null ? formatRemaining(remaining) : remainingSec != null ? formatRemaining(Math.max(0, Number(remainingSec) || 0)) : null

  if (display == null) {
    return (
      <span className="quests-card-timer-chip" role="timer" aria-live="polite">
        ⏳ идёт
      </span>
    )
  }

  return (
    <span className="quests-card-timer-chip" role="timer" aria-live="polite">
      ⏳ {display}
    </span>
  )
}

function PeriodTimerBadge({ remainingSec }) {
  const remaining = useServerRemainingTimer(remainingSec)
  const display = remaining != null
    ? formatRemaining(remaining)
    : remainingSec != null
      ? formatRemaining(Math.max(0, Number(remainingSec) || 0))
      : null
  if (display == null) return null
  return (
    <span className="quests-section-timer" role="timer" aria-live="off" title="До сброса всех заданий периода">
      🔄 {display}
    </span>
  )
}

const PERIOD_RESET_HINT = {
  hourly: '2 на выбор · взять можно одно · сброс каждый час (:00)',
  daily: '3 на выбор · взять можно одно · сброс в 00:00 МСК',
  weekly: '1 марафон · сброс по понедельникам',
  events: 'По датам ивента',
}

function DailySeedQuest({
  quest,
  seedEconomy,
  farmCrops,
  claiming,
  onClaim,
}) {
  const plantableCrops = (farmCrops ?? []).filter((crop) => crop.seedId)
  const dropPercent = seedEconomy?.harvestDropPercent ?? 25
  const amount = seedEconomy?.dailySeedAmount ?? 1
  const claimedToday = seedEconomy?.dailySeedClaimedToday

  if (claimedToday) {
    return (
      <p className="quests-seed-status quests-seed-status--done">
        ✅ Уже получено.
      </p>
    )
  }

  return (
    <div className="quests-seed-picker">
      <p className="quests-seed-status">
        Выбери семена и забери {amount} шт. бесплатно. Не занимает слот дневного задания.
      </p>
      <div className="quests-seed-choices" role="group" aria-label="Выбор семян">
        {plantableCrops.length ? (
          plantableCrops.map((crop) => (
            <button
              key={crop.seedId}
              type="button"
              className="quests-seed-choice"
              disabled={claiming}
              onClick={() => onClaim?.(crop.seedId)}
            >
              <span aria-hidden>{crop.seedEmoji ?? '🌱'}</span>
              <span>{crop.seedName ?? crop.displayName}</span>
            </button>
          ))
        ) : (
          <button
            type="button"
            className="quests-seed-choice"
            disabled={claiming}
            onClick={() => onClaim?.(null)}
          >
            <span aria-hidden>🌱</span>
            <span>Получить семена</span>
          </button>
        )}
      </div>
    </div>
  )
}

function QuestCard({
  quest,
  fallbackRemainingSec,
  claiming,
  accepting,
  canceling,
  onAccept,
  onClaim,
  onCancel,
  onExpire,
  seedEconomy,
  farmCrops,
  claimingDailySeed,
  onClaimDailySeed,
}) {
  const isDailySeed = quest.action === 'claim_daily_seed'
  const isActiveQuest = Boolean(
    quest.accepted
      || quest.acceptedAt
      || quest.periodEndsAt
      || quest.timerRemainingSec != null,
  ) && !isDailySeed
  const canCancelQuest = Boolean(quest.canCancel || (isActiveQuest && !quest.claimed))
  const timerRemainingSec = quest.timerRemainingSec ?? fallbackRemainingSec
  const progressPct = quest.target > 0
    ? Math.min(100, Math.round((quest.progress / quest.target) * 100))
    : 0

  let cardMod = ''
  if (quest.claimed) cardMod = 'quests-card--done'
  else if (quest.ready) cardMod = 'quests-card--ready'
  else if (isActiveQuest) cardMod = 'quests-card--active'
  else if (quest.locked) cardMod = 'quests-card--locked'

  return (
    <article className={`quests-card ${cardMod}`.trim()}>
      <div className="quests-card-head">
        <span className="quests-card-emoji" aria-hidden>{quest.emoji}</span>
        <div className="quests-card-copy">
          <h3 className="quests-card-title">{quest.title}</h3>
          <p className="quests-card-desc">{quest.description}</p>
          {quest.targetHint ? (
            <p className="quests-card-target">{quest.targetHint}</p>
          ) : null}
          {isActiveQuest && !quest.claimed ? (
            <p className="quests-card-timer-caption">До обновления периода</p>
          ) : null}
        </div>
        {quest.claimed ? (
          <span className="quests-card-badge quests-card-badge--done" aria-label="Выполнено">✓</span>
        ) : isActiveQuest ? (
          <QuestTimerChip remainingSec={timerRemainingSec} onExpire={onExpire} />
        ) : quest.ready ? (
          <span className="quests-card-badge quests-card-badge--ready">!</span>
        ) : null}
      </div>

      {isDailySeed ? (
        <DailySeedQuest
          quest={quest}
          seedEconomy={seedEconomy}
          farmCrops={farmCrops}
          claiming={claimingDailySeed}
          onClaim={onClaimDailySeed}
        />
      ) : (
        <>
          {quest.locked ? (
            <p className="quests-card-lock">
              Слот занят: «{quest.activeQuestTitle ?? 'другое задание'}»
            </p>
          ) : null}

          {isActiveQuest ? (
            <div className="quests-progress">
              <div className="quests-progress-track">
                <div className="quests-progress-fill" style={{ width: `${progressPct}%` }} />
              </div>
              <span className="quests-progress-label">
                {quest.progress}/{quest.target}
              </span>
            </div>
          ) : null}

          <div className="quests-card-foot">
            <p className="quests-reward">
              <span className="quests-reward-icon" aria-hidden>🎁</span>
              <span className="quests-reward-text">{rewardLabel(quest.rewards)}</span>
            </p>

            {quest.claimed ? (
              <span className="quests-status-pill quests-status-pill--done">Готово</span>
            ) : quest.canAccept ? (
              <button
                type="button"
                className="quests-action-btn quests-action-btn--accept"
                disabled={accepting}
                onClick={() => onAccept?.(quest.id)}
              >
                {accepting ? 'Берём…' : 'Взять'}
              </button>
            ) : isActiveQuest ? (
              <div className="quests-card-actions">
                {canCancelQuest ? (
                  <button
                    type="button"
                    className="quests-action-btn quests-action-btn--cancel"
                    disabled={canceling}
                    onClick={() => onCancel?.(quest.id)}
                  >
                    {canceling ? '…' : 'Отменить'}
                  </button>
                ) : null}
                <button
                  type="button"
                  className="quests-action-btn quests-action-btn--claim"
                  disabled={!quest.ready || claiming}
                  onClick={() => onClaim?.(quest.id)}
                >
                  {claiming ? 'Выдаём…' : quest.ready ? 'Забрать' : 'В процессе'}
                </button>
              </div>
            ) : quest.locked ? (
              <span className="quests-status-pill">Занято</span>
            ) : null}
          </div>
        </>
      )}
    </article>
  )
}

export default function QuestsModule({ isActive = true }) {
  const expireReloadingRef = useRef(false)
  const {
    kut,
    sections,
    readyCount,
    npcName,
    npcEmoji,
    periodLabels,
    periodTimers,
    acceptRules,
    seedEconomy,
    farmCrops,
    initialLoading,
    refreshing,
    error,
    errorCode,
    claimingQuestId,
    acceptingQuestId,
    cancelingQuestId,
    claimingDailySeed,
    questMessage,
    claimQuest,
    acceptQuest,
    cancelQuest,
    claimDailySeed,
    reload,
  } = useQuests({ isActive })

  const {
    donateOpen,
    openDonate,
    closeDonate,
  } = useContextualDonate()

  const totalQuests = useMemo(
    () => PERIOD_ORDER.reduce((sum, key) => sum + (sections[key]?.length ?? 0), 0),
    [sections],
  )

  const doneQuests = useMemo(
    () => PERIOD_ORDER.reduce(
      (sum, key) => sum + (sections[key]?.filter((quest) => quest.claimed).length ?? 0),
      0,
    ),
    [sections],
  )

  const handleTimerExpire = async () => {
    if (expireReloadingRef.current) return
    expireReloadingRef.current = true
    try {
      await reload()
    } finally {
      expireReloadingRef.current = false
    }
  }

  return (
    <div className="relative min-h-screen tab-theme-quests quests-module">
      <FarmBackground />
      <TabAtmosphere variant="quests" />

      <div className="relative z-10 quests-shell py-4 pb-2 animate-slide-up">
        <header className="quests-hero">
          <div className="quests-hero-identity">
            <div className="quests-npc-avatar" aria-hidden>{npcEmoji}</div>
            <div className="quests-hero-copy">
              <h1 className="quests-hero-title">{npcName}</h1>
            </div>
          </div>

          <div className="quests-hero-wallet">
            <KutBalance
              value={kut}
              className="quests-hero-balance"
              onDonate={openDonate}
            />
          </div>
        </header>

        <div className="quests-summary" role="status">
          <span className="quests-summary-chip">
            {doneQuests}/{totalQuests} выполнено
          </span>
          {readyCount > 0 ? (
            <span className="quests-summary-chip quests-summary-chip--hot">
              {readyCount} награда ждет
            </span>
          ) : null}
        </div>

        {questMessage ? (
          <p className="quests-toast quests-toast-ok" role="status">{questMessage}</p>
        ) : null}

        {error ? (
          <p className={`quests-toast ${errorClass(errorCode)}`} role="alert">{error}</p>
        ) : null}

        <VineFrame className="quests-frame">
          <div className="quests-panel">
            {initialLoading ? (
              <div className="quests-loading">
                <span className="quests-loading-emoji" aria-hidden>📜</span>
                <p>Готовим задания…</p>
              </div>
            ) : (
              PERIOD_ORDER.map((period) => {
                const quests = sections[period] ?? []
                if (!quests.length) return null

                const activeQuests = quests.filter(
                  (quest) => (quest.accepted || quest.acceptedAt || quest.timerRemainingSec != null)
                    && !quest.claimed
                    && quest.action !== 'claim_daily_seed',
                )
                const slotLimit = acceptRules?.[period] ?? 1
                const readyInSection = quests.filter((quest) => quest.ready && !quest.claimed).length
                const resetHint = PERIOD_RESET_HINT[period] ?? 'Сброс по расписанию'
                const activeMeta = activeQuests.length
                  ? ` · ${activeQuests.length}/${slotLimit} в работе`
                  : ''

                return (
                  <section key={period} className="quests-section">
                    <div className="quests-section-head">
                      <span className="quests-section-icon" aria-hidden>{PERIOD_ICONS[period]}</span>
                      <div className="quests-section-copy">
                        <span className="quests-section-title">{periodLabels[period] ?? period}</span>
                        <span className="quests-section-meta">
                          {resetHint}
                          {activeMeta}
                        </span>
                      </div>
                      <div className="quests-section-right">
                        <PeriodTimerBadge remainingSec={periodTimers?.[period]?.timerRemainingSec} />
                        {readyInSection > 0 ? (
                          <span className="quests-section-badge">{readyInSection}</span>
                        ) : null}
                      </div>
                    </div>

                    <div className="quests-section-list">
                      {quests.map((quest) => (
                        <QuestCard
                          key={quest.id}
                          quest={quest}
                          fallbackRemainingSec={periodTimers?.[period]?.timerRemainingSec}
                          claiming={claimingQuestId === quest.id}
                          accepting={acceptingQuestId === quest.id}
                          canceling={cancelingQuestId === quest.id}
                          onAccept={acceptQuest}
                          onClaim={claimQuest}
                          onCancel={cancelQuest}
                          onExpire={handleTimerExpire}
                          seedEconomy={seedEconomy}
                          farmCrops={farmCrops}
                          claimingDailySeed={claimingDailySeed}
                          onClaimDailySeed={claimDailySeed}
                        />
                      ))}
                    </div>
                  </section>
                )
              })
            )}

            {refreshing && !initialLoading ? (
              <p className="quests-refresh-hint" aria-live="polite">Обновляем…</p>
            ) : null}
          </div>
        </VineFrame>
      </div>

      <DonateModal isOpen={donateOpen} onClose={closeDonate} />
    </div>
  )
}
