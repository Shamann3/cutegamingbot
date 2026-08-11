import { useEffect, useId, useMemo, useRef, useState } from 'react'

const DEFAULT_CHAT = '@CuteGamingChat'

/** Лестница путей: старт и цель подобраны вручную, награда/ставка/слоты считаются. */
const LADDER = [
  { start: 25, target: 120, free: '+', tag: 'Микро', blurb: 'Самый лёгкий вход' },
  { start: 30, target: 150, free: '+', tag: 'Микро+', blurb: 'Короткий бесплатный путь' },
  { start: 50, target: 250, free: '+', tag: 'Лёгкий', blurb: 'Удобный старт для новичков' },
  { start: 100, target: 500, free: '+', tag: 'Базовый', blurb: 'Классический бесплатный путь' },
  { start: 100, target: 650, free: '+', tag: 'Базовый+', blurb: 'Чуть длиннее, та же зона' },
  { start: 120, target: 750, free: '+', tag: 'Средний free', blurb: 'Для тех, кто уже играл' },
  { start: 25, target: 120, free: '-', tag: 'Микро платный', blurb: 'Малый депозит, быстрый цикл' },
  { start: 50, target: 250, free: '-', tag: 'Лёгкий платный', blurb: 'Недорогой обычный челлендж' },
  { start: 80, target: 400, free: '-', tag: 'Старт+', blurb: 'Средний темп' },
  { start: 100, target: 600, free: '-', tag: 'Средний', blurb: 'Основной платный сегмент' },
  { start: 150, target: 800, free: '-', tag: 'Средний+', blurb: 'Чуть выше среднего' },
  { start: 200, target: 1200, free: '-', tag: 'Профи', blurb: 'Для уверенных игроков' },
  { start: 300, target: 1800, free: '-', tag: 'Профи+', blurb: 'Длинный путь' },
  { start: 400, target: 2200, free: '-', tag: 'Верхний', blurb: 'Высокий старт' },
  { start: 500, target: 3000, free: '-', tag: 'Кит', blurb: 'Крупный сегмент' },
  { start: 800, target: 4500, free: '-', tag: 'Кит+', blurb: 'Редкий сложный путь' },
  { start: 1000, target: 5000, free: '-', tag: 'Хард', blurb: 'Для самых крупных' },
  { start: 2000, target: 10000, free: '-', tag: 'Экстрим', blurb: 'Максимальная сложность' },
]

function roundNice(n) {
  const x = Number(n)
  if (!Number.isFinite(x) || x <= 0) return 1
  if (x < 10) return Math.max(1, Math.round(x))
  if (x < 50) return Math.round(x)
  if (x < 200) return Math.round(x / 5) * 5
  if (x < 1000) return Math.round(x / 10) * 10
  return Math.round(x / 50) * 50
}

/** ~2.4–2.8% от пути (цель − старт), с разумными границами. */
export function calcChallengeReward(start, target, free = '-') {
  const s = Math.max(0, Number(start) || 0)
  const t = Math.max(0, Number(target) || 0)
  const gap = Math.max(0, t - s)
  if (gap <= 0) return 1
  const rate = free === '+' ? 0.028 : 0.024
  let reward = roundNice(gap * rate)
  if (gap <= 100) reward = Math.max(2, Math.min(reward, 8))
  else if (gap <= 500) reward = Math.max(5, Math.min(reward, 40))
  else if (gap <= 2000) reward = Math.max(12, Math.min(reward, 120))
  else reward = Math.max(40, reward)
  const hardCap = Math.max(1, Math.floor(gap * 0.08))
  return Math.max(1, Math.min(reward, hardCap))
}

export function calcChallengeMaxBet(start, free = '-') {
  if (free === '+') return ''
  const s = Math.max(1, Number(start) || 1)
  return String(roundNice(Math.max(5, s * 0.45)))
}

export function calcChallengeMaxUsers(start, target, free = '-') {
  const s = Math.max(0, Number(start) || 0)
  const t = Math.max(0, Number(target) || 0)
  const gap = Math.max(0, t - s)
  if (free === '+') {
    if (gap <= 150) return '50'
    if (gap <= 400) return '35'
    if (gap <= 700) return '25'
    return '15'
  }
  if (s >= 1000) return '5'
  if (s >= 500) return '8'
  if (s >= 200) return '12'
  if (s >= 80) return '20'
  return '30'
}

function uid() {
  return Math.random().toString(36).slice(2, 10)
}

function buildRow(blueprint, { chatRef, startsAt }) {
  const free = blueprint.free === '+' ? '+' : '-'
  const start = blueprint.start
  const target = blueprint.target
  return {
    key: uid(),
    selected: true,
    autoReward: true,
    autoLimits: true,
    tag: blueprint.tag,
    blurb: blueprint.blurb,
    startAmount: String(start),
    targetAmount: String(target),
    rewardAmount: String(calcChallengeReward(start, target, free)),
    maxBet: calcChallengeMaxBet(start, free),
    maxUsers: calcChallengeMaxUsers(start, target, free),
    free,
    chatRef: chatRef || DEFAULT_CHAT,
    startsAt: startsAt || '',
  }
}

export function buildSuggestedChallenges({ chatRef = DEFAULT_CHAT, startsAt = '' } = {}) {
  return LADDER.map((bp) => buildRow(bp, { chatRef, startsAt }))
}

function num(v) {
  const n = Number(String(v).replace(',', '.').trim())
  return Number.isFinite(n) ? n : NaN
}

function validateRow(row) {
  const start = num(row.startAmount)
  const target = num(row.targetAmount)
  const reward = num(row.rewardAmount)
  if (!Number.isFinite(start) || start <= 0) return 'Старт должен быть > 0'
  if (!Number.isFinite(target) || target <= 0) return 'Цель должна быть > 0'
  if (!(target > start)) return 'Цель должна быть больше старта'
  if (!Number.isFinite(reward) || reward <= 0) return 'Награда должна быть > 0'
  if (row.free !== '+' && row.maxBet !== '' && num(row.maxBet) <= 0) return 'Макс. ставка некорректна'
  if (row.maxUsers !== '' && num(row.maxUsers) <= 0) return 'Слоты должны быть > 0'
  return null
}

function isDuplicate(row, existing) {
  const start = num(row.startAmount)
  const target = num(row.targetAmount)
  const free = row.free === '+' ? '+' : '-'
  const chat = (row.chatRef || '').trim().toLowerCase()
  return (existing || []).some((g) => {
    if (g.status === 'disabled') return false
    const gChat = (g.targetChatRef || '').trim().toLowerCase()
    return (
      Number(g.startAmount) === start
      && Number(g.targetAmount) === target
      && (g.free === '+' ? '+' : '-') === free
      && gChat === chat
    )
  })
}

function gapOf(row) {
  const s = num(row.startAmount)
  const t = num(row.targetAmount)
  if (!Number.isFinite(s) || !Number.isFinite(t)) return 0
  return Math.max(0, t - s)
}

function rewardPct(row) {
  const gap = gapOf(row)
  const r = num(row.rewardAmount)
  if (!gap || !Number.isFinite(r)) return null
  return (r / gap) * 100
}

/**
 * Полноэкранное окно: предложить → выбрать → подправить → создать.
 */
export default function BotChallengeSuggestModal({
  open,
  existing = [],
  onClose,
  onCreate,
}) {
  const titleId = useId()
  const panelRef = useRef(null)
  const existingRef = useRef(existing)
  existingRef.current = existing
  const [rows, setRows] = useState([])
  const [filter, setFilter] = useState('all')
  const [sharedChat, setSharedChat] = useState(DEFAULT_CHAT)
  const [sharedStart, setSharedStart] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return undefined
    const pack = buildSuggestedChallenges({ chatRef: DEFAULT_CHAT, startsAt: '' }).map((row) => ({
      ...row,
      selected: !isDuplicate(row, existingRef.current),
    }))
    setRows(pack)
    setFilter('all')
    setSharedChat(DEFAULT_CHAT)
    setSharedStart('')
    setSaving(false)
    setError('')
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const prev = document.activeElement
    const t = window.setTimeout(() => {
      panelRef.current?.querySelector('button, input')?.focus?.()
    }, 0)
    return () => {
      document.body.style.overflow = prevOverflow
      window.clearTimeout(t)
      if (prev && typeof prev.focus === 'function') {
        try { prev.focus() } catch { /* ignore */ }
      }
    }
  }, [open])

  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape' && !saving) onClose?.()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, saving, onClose])

  const visible = useMemo(() => {
    if (filter === 'free') return rows.filter((r) => r.free === '+')
    if (filter === 'paid') return rows.filter((r) => r.free !== '+')
    return rows
  }, [rows, filter])

  const selected = useMemo(() => rows.filter((r) => r.selected), [rows])
  const selectedValid = useMemo(
    () => selected.filter((r) => !validateRow(r) && !isDuplicate(r, existing)),
    [selected, existing],
  )

  const patchRow = (key, patch, { touchReward = false, touchLimits = false } = {}) => {
    setRows((list) => list.map((row) => {
      if (row.key !== key) return row
      let next = { ...row, ...patch }
      if (touchReward && next.autoReward) {
        next.rewardAmount = String(calcChallengeReward(next.startAmount, next.targetAmount, next.free))
      }
      if (touchLimits && next.autoLimits) {
        next.maxBet = calcChallengeMaxBet(next.startAmount, next.free)
        next.maxUsers = calcChallengeMaxUsers(next.startAmount, next.targetAmount, next.free)
      }
      return next
    }))
  }

  const applyShared = () => {
    setRows((list) => list.map((row) => ({
      ...row,
      chatRef: sharedChat.trim() || DEFAULT_CHAT,
      startsAt: sharedStart,
    })))
  }

  const setAllVisible = (value) => {
    const keys = new Set(visible.map((r) => r.key))
    setRows((list) => list.map((row) => (keys.has(row.key) ? { ...row, selected: value } : row)))
  }

  const recalcSelected = () => {
    setRows((list) => list.map((row) => {
      if (!row.selected) return row
      return {
        ...row,
        autoReward: true,
        autoLimits: true,
        rewardAmount: String(calcChallengeReward(row.startAmount, row.targetAmount, row.free)),
        maxBet: calcChallengeMaxBet(row.startAmount, row.free),
        maxUsers: calcChallengeMaxUsers(row.startAmount, row.targetAmount, row.free),
      }
    }))
  }

  const handleCreate = async () => {
    setError('')
    const payload = selectedValid.map((row) => ({
      startAmount: Number(row.startAmount),
      targetAmount: Number(row.targetAmount),
      rewardAmount: Number(row.rewardAmount),
      maxBet: row.free === '+' || row.maxBet === '' ? null : Number(row.maxBet),
      maxUsers: row.maxUsers === '' ? null : Number(row.maxUsers),
      free: row.free === '+' ? '+' : '-',
      chatRef: (row.chatRef || DEFAULT_CHAT).trim() || DEFAULT_CHAT,
      startsAt: row.startsAt ? new Date(row.startsAt).toISOString() : null,
    }))
    if (!payload.length) {
      setError('Выберите хотя бы одно корректное задание без дублей')
      return
    }
    setSaving(true)
    try {
      await onCreate?.(payload)
      onClose?.()
    } catch (e) {
      setError(e?.message || 'Не удалось создать челленджи')
    } finally {
      setSaving(false)
    }
  }

  if (!open) return null

  return (
    <div
      className="bq-auto-backdrop"
      role="presentation"
      onClick={() => { if (!saving) onClose?.() }}
    >
      <div
        ref={panelRef}
        className="bq-auto-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="bq-auto-head">
          <div>
            <p className="bq-kicker">Автоподбор</p>
            <h3 id={titleId}>Создание челленджей автоматически</h3>
            <p className="bq-auto-lead">
              Система предлагает лестницу путей: старт, цель, награда (~2–3% от пути),
              макс. ставку и слоты. Отметь нужные, при желании подправь и создай.
            </p>
          </div>
          <button type="button" className="bq-btn bq-btn-ghost" disabled={saving} onClick={onClose}>
            Закрыть
          </button>
        </header>

        <div className="bq-auto-shared">
          <label className="bq-field">
            <span>Чат для всех</span>
            <input
              className="bq-input"
              value={sharedChat}
              onChange={(e) => setSharedChat(e.target.value)}
              placeholder={DEFAULT_CHAT}
            />
          </label>
          <label className="bq-field">
            <span>Старт для всех</span>
            <input
              className="bq-input"
              type="datetime-local"
              value={sharedStart}
              onChange={(e) => setSharedStart(e.target.value)}
            />
          </label>
          <button type="button" className="bq-btn bq-btn-ghost" onClick={applyShared} disabled={saving}>
            Применить ко всем
          </button>
          <button type="button" className="bq-btn bq-btn-ghost" onClick={recalcSelected} disabled={saving}>
            Пересчитать награды
          </button>
        </div>

        <div className="bq-auto-toolbar">
          <div className="bq-filters">
            {[
              ['all', 'Все'],
              ['free', 'Бесплатные'],
              ['paid', 'Обычные'],
            ].map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={`bq-pill${filter === id ? ' is-active' : ''}`}
                onClick={() => setFilter(id)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="bq-auto-sel">
            <button type="button" className="bq-link" onClick={() => setAllVisible(true)}>Выбрать видимые</button>
            <button type="button" className="bq-link" onClick={() => setAllVisible(false)}>Снять</button>
            <span>{selected.length} выбрано · к созданию {selectedValid.length}</span>
          </div>
        </div>

        <div className="bq-auto-body">
          {visible.map((row, idx) => {
            const err = validateRow(row)
            const dup = isDuplicate(row, existing)
            const pct = rewardPct(row)
            const gap = gapOf(row)
            return (
              <article
                key={row.key}
                className={`bq-auto-card${row.selected ? ' is-selected' : ''}${dup ? ' is-dup' : ''}${err ? ' is-bad' : ''}`}
                style={{ '--i': idx % 10 }}
              >
                <label className="bq-auto-check">
                  <input
                    type="checkbox"
                    checked={row.selected}
                    disabled={dup}
                    onChange={(e) => patchRow(row.key, { selected: e.target.checked })}
                  />
                  <span className="bq-auto-box" aria-hidden="true" />
                </label>

                <div className="bq-auto-main">
                  <div className="bq-auto-top">
                    <strong>{row.tag}</strong>
                    <span className={`bq-pay-kind is-${row.free === '+' ? 'sub' : 'gc'}`}>
                      {row.free === '+' ? 'Бесплатный' : 'Обычный'}
                    </span>
                    {dup && <span className="bq-auto-flag">Уже есть</span>}
                    {err && row.selected && <span className="bq-auto-flag is-err">{err}</span>}
                  </div>
                  <p className="bq-auto-blurb">{row.blurb}</p>

                  <div className="bq-auto-grid">
                    <label className="bq-field">
                      <span>Старт</span>
                      <input
                        className="bq-input"
                        inputMode="numeric"
                        value={row.startAmount}
                        onChange={(e) => patchRow(row.key, { startAmount: e.target.value }, { touchReward: true, touchLimits: true })}
                      />
                    </label>
                    <label className="bq-field">
                      <span>Цель</span>
                      <input
                        className="bq-input"
                        inputMode="numeric"
                        value={row.targetAmount}
                        onChange={(e) => patchRow(row.key, { targetAmount: e.target.value }, { touchReward: true, touchLimits: true })}
                      />
                    </label>
                    <label className="bq-field">
                      <span>Награда {row.autoReward ? '· авто' : '· вручную'}</span>
                      <input
                        className="bq-input"
                        inputMode="numeric"
                        value={row.rewardAmount}
                        onChange={(e) => patchRow(row.key, { rewardAmount: e.target.value, autoReward: false })}
                      />
                    </label>
                    <label className="bq-field">
                      <span>Макс. ставка</span>
                      <input
                        className="bq-input"
                        inputMode="numeric"
                        value={row.maxBet}
                        disabled={row.free === '+'}
                        placeholder={row.free === '+' ? 'не нужна' : ''}
                        onChange={(e) => patchRow(row.key, { maxBet: e.target.value, autoLimits: false })}
                      />
                    </label>
                    <label className="bq-field">
                      <span>Слоты</span>
                      <input
                        className="bq-input"
                        inputMode="numeric"
                        value={row.maxUsers}
                        placeholder="без лимита"
                        onChange={(e) => patchRow(row.key, { maxUsers: e.target.value, autoLimits: false })}
                      />
                    </label>
                    <label className="bq-field">
                      <span>Тип</span>
                      <select
                        className="bq-input"
                        value={row.free}
                        onChange={(e) => patchRow(
                          row.key,
                          { free: e.target.value === '+' ? '+' : '-' },
                          { touchReward: true, touchLimits: true },
                        )}
                      >
                        <option value="+">Бесплатный</option>
                        <option value="-">Обычный</option>
                      </select>
                    </label>
                    <label className="bq-field bq-auto-span2">
                      <span>Чат</span>
                      <input
                        className="bq-input"
                        value={row.chatRef}
                        onChange={(e) => patchRow(row.key, { chatRef: e.target.value })}
                      />
                    </label>
                    <label className="bq-field bq-auto-span2">
                      <span>Когда показать</span>
                      <input
                        className="bq-input"
                        type="datetime-local"
                        value={row.startsAt}
                        onChange={(e) => patchRow(row.key, { startsAt: e.target.value })}
                      />
                    </label>
                  </div>

                  <div className="bq-auto-stats">
                    <span>Путь <b>{gap || '—'}</b></span>
                    <span>Награда <b>{pct != null ? `${pct.toFixed(1)}%` : '—'}</b> от пути</span>
                    <span>{row.startAmount || '?'} → {row.targetAmount || '?'} · +{row.rewardAmount || '?'}</span>
                  </div>
                </div>
              </article>
            )
          })}
        </div>

        <footer className="bq-auto-foot">
          <div className="bq-auto-foot-msg">
            {error ? <span className="bq-auto-error">{error}</span> : (
              <span>
                Создадутся только отмеченные и валидные задания.
                Дубликаты пропускаются.
              </span>
            )}
          </div>
          <div className="bq-auto-foot-actions">
            <button type="button" className="bq-btn bq-btn-ghost" disabled={saving} onClick={onClose}>
              Отмена
            </button>
            <button
              type="button"
              className="bq-btn bq-btn-primary"
              disabled={saving || selectedValid.length === 0}
              onClick={handleCreate}
            >
              {saving
                ? 'Создаю…'
                : `Создать ${selectedValid.length} ${selectedValid.length === 1 ? 'челлендж' : 'челленджей'}`}
            </button>
          </div>
        </footer>
      </div>
    </div>
  )
}
