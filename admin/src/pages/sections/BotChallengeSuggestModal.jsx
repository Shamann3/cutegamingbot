import { useEffect, useId, useMemo, useRef, useState } from 'react'

const DEFAULT_CHAT = '@CuteGamingChat'

/**
 * Тиры лестницы: ищем свободные (start, target), которых ещё нет.
 * want — сколько новых предложений на тир.
 */
const TIERS = [
  {
    id: 'micro-free',
    free: '+',
    tag: 'Микро',
    blurb: 'Лёгкий бесплатный вход',
    want: 2,
    starts: [20, 25, 28, 30, 35, 40, 45],
    mults: [4, 4.5, 5, 5.5, 6],
  },
  {
    id: 'easy-free',
    free: '+',
    tag: 'Лёгкий',
    blurb: 'Комфортный бесплатный путь',
    want: 2,
    starts: [50, 55, 60, 70, 75, 80, 90],
    mults: [4, 4.5, 5, 5.5, 6],
  },
  {
    id: 'base-free',
    free: '+',
    tag: 'Базовый',
    blurb: 'Классическая бесплатная зона',
    want: 2,
    starts: [100, 110, 120, 130, 140, 150],
    mults: [4.5, 5, 5.5, 6, 6.5],
  },
  {
    id: 'mid-free',
    free: '+',
    tag: 'Средний free',
    blurb: 'Длиннее обычного бесплатного',
    want: 1,
    starts: [160, 180, 200, 220, 250],
    mults: [5, 5.5, 6, 6.5, 7],
  },
  {
    id: 'micro-paid',
    free: '-',
    tag: 'Микро платный',
    blurb: 'Малый депозит, быстрый цикл',
    want: 2,
    starts: [20, 25, 30, 35, 40, 45],
    mults: [4, 4.5, 5, 5.5],
  },
  {
    id: 'easy-paid',
    free: '-',
    tag: 'Лёгкий платный',
    blurb: 'Недорогой обычный челлендж',
    want: 2,
    starts: [50, 60, 70, 80, 90],
    mults: [4, 4.5, 5, 5.5, 6],
  },
  {
    id: 'mid-paid',
    free: '-',
    tag: 'Средний',
    blurb: 'Основной платный сегмент',
    want: 2,
    starts: [100, 120, 140, 150, 160, 180],
    mults: [5, 5.5, 6, 6.5, 7],
  },
  {
    id: 'pro-paid',
    free: '-',
    tag: 'Профи',
    blurb: 'Для уверенных игроков',
    want: 2,
    starts: [200, 220, 250, 280, 300, 350],
    mults: [5, 5.5, 6, 6.5, 7],
  },
  {
    id: 'upper-paid',
    free: '-',
    tag: 'Верхний',
    blurb: 'Высокий старт',
    want: 1,
    starts: [400, 450, 500, 550, 600],
    mults: [5, 5.5, 6, 6.5],
  },
  {
    id: 'whale-paid',
    free: '-',
    tag: 'Кит',
    blurb: 'Крупный сегмент',
    want: 1,
    starts: [700, 800, 900, 1000, 1200],
    mults: [4.5, 5, 5.5, 6],
  },
  {
    id: 'hard-paid',
    free: '-',
    tag: 'Хард',
    blurb: 'Редкий сложный путь',
    want: 1,
    starts: [1500, 1800, 2000, 2500],
    mults: [4.5, 5, 5.5, 6],
  },
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

function num(v) {
  const n = Number(String(v).replace(',', '.').trim())
  return Number.isFinite(n) ? n : NaN
}

function normChat(raw) {
  return (raw || '').trim().toLowerCase() || DEFAULT_CHAT.toLowerCase()
}

function sigKey(start, target, free, chat) {
  return `${Number(start)}|${Number(target)}|${free === '+' ? '+' : '-'}|${normChat(chat)}`
}

function mulberry32(seed) {
  let a = seed >>> 0
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function shuffle(list, rand) {
  const arr = [...list]
  for (let i = arr.length - 1; i > 0; i -= 1) {
    const j = Math.floor(rand() * (i + 1))
    ;[arr[i], arr[j]] = [arr[j], arr[i]]
  }
  return arr
}

/** Занятые точные ключи + список для проверки «слишком похоже». */
function buildOccupied(existing, chatRef) {
  const exact = new Set()
  const paths = []
  const chat = normChat(chatRef)
  for (const g of existing || []) {
    const free = g.free === '+' ? '+' : '-'
    const gChat = normChat(g.targetChatRef || chatRef)
    // Считаем занятым любой статус — иначе снова предложим то же самое
    const start = Number(g.startAmount)
    const target = Number(g.targetAmount)
    if (!Number.isFinite(start) || !Number.isFinite(target)) continue
    exact.add(sigKey(start, target, free, gChat))
    if (gChat === chat || !g.targetChatRef) {
      paths.push({ start, target, free, chat: gChat })
    }
  }
  return { exact, paths }
}

/**
 * Слишком похоже: тот же тип + тот же старт и цель в пределах ~10%,
 * либо почти идентичный путь (старт ±8% и цель ±8%).
 */
function isTooSimilar(start, target, free, chat, paths) {
  const f = free === '+' ? '+' : '-'
  const c = normChat(chat)
  for (const p of paths) {
    if (p.free !== f) continue
    if (p.chat && p.chat !== c && c === normChat(DEFAULT_CHAT)) {
      // сравниваем в основном в рамках выбранного чата
    }
    if (p.chat && c && p.chat !== c) continue

    if (p.start === start) {
      const denom = Math.max(p.target, target, 1)
      if (Math.abs(p.target - target) / denom < 0.1) return true
    }

    const startDen = Math.max(p.start, start, 1)
    const targetDen = Math.max(p.target, target, 1)
    if (
      Math.abs(p.start - start) / startDen < 0.08
      && Math.abs(p.target - target) / targetDen < 0.08
    ) {
      return true
    }
  }
  return false
}

function candidateOk(start, target, free, chat, exact, paths) {
  if (!(target > start)) return false
  const key = sigKey(start, target, free, chat)
  if (exact.has(key)) return false
  if (isTooSimilar(start, target, free, chat, paths)) return false
  return true
}

function reserve(start, target, free, chat, exact, paths) {
  exact.add(sigKey(start, target, free, chat))
  paths.push({ start, target, free: free === '+' ? '+' : '-', chat: normChat(chat) })
}

function buildRowFromPath({ start, target, free, tag, blurb, chatRef, startsAt, fresh }) {
  const f = free === '+' ? '+' : '-'
  return {
    key: uid(),
    selected: true,
    autoReward: true,
    autoLimits: true,
    tag,
    blurb,
    fresh: Boolean(fresh),
    startAmount: String(start),
    targetAmount: String(target),
    rewardAmount: String(calcChallengeReward(start, target, f)),
    maxBet: calcChallengeMaxBet(start, f),
    maxUsers: calcChallengeMaxUsers(start, target, f),
    free: f,
    chatRef: chatRef || DEFAULT_CHAT,
    startsAt: startsAt || '',
  }
}

/**
 * Подбирает полностью новые челленджи под уже существующие.
 * Никогда не возвращает точный дубль и избегает слишком похожих путей.
 */
export function buildSuggestedChallenges({
  existing = [],
  chatRef = DEFAULT_CHAT,
  startsAt = '',
  seed = Date.now(),
  limit = 16,
} = {}) {
  const rand = mulberry32(Number(seed) || 1)
  const chat = (chatRef || DEFAULT_CHAT).trim() || DEFAULT_CHAT
  const { exact, paths } = buildOccupied(existing, chat)
  const out = []

  const tiers = shuffle(TIERS, rand)
  for (const tier of tiers) {
    if (out.length >= limit) break
    const free = tier.free === '+' ? '+' : '-'
    let made = 0
    const starts = shuffle(tier.starts, rand)
    const mults = shuffle(tier.mults, rand)

    for (const startRaw of starts) {
      if (made >= tier.want || out.length >= limit) break
      for (const mult of mults) {
        if (made >= tier.want || out.length >= limit) break
        const start = roundNice(startRaw)
        let target = roundNice(start * mult)
        if (target <= start) target = roundNice(start + Math.max(40, start * 2))

        // Небольшие сдвиги цели, если близко к занятому
        const targetTweaks = [0, 10, -10, 20, -20, 30, 40, 50, -30, 75, 100]
        let placed = false
        for (const tw of targetTweaks) {
          const t = roundNice(Math.max(start + 10, target + tw))
          if (!candidateOk(start, t, free, chat, exact, paths)) continue
          reserve(start, t, free, chat, exact, paths)
          out.push(buildRowFromPath({
            start,
            target: t,
            free,
            tag: tier.tag,
            blurb: `${tier.blurb} · новый путь`,
            chatRef: chat,
            startsAt,
            fresh: true,
          }))
          made += 1
          placed = true
          break
        }
        if (placed) break
      }
    }

    // Если тир всё ещё пуст — сдвиг старта
    if (made < tier.want && out.length < limit) {
      for (let step = 1; step <= 40 && made < tier.want && out.length < limit; step += 1) {
        const base = tier.starts[step % tier.starts.length]
        const start = roundNice(base + step * (free === '+' ? 3 : 5))
        const mult = tier.mults[step % tier.mults.length]
        const target = roundNice(start * mult)
        if (!candidateOk(start, target, free, chat, exact, paths)) continue
        reserve(start, target, free, chat, exact, paths)
        out.push(buildRowFromPath({
          start,
          target,
          free,
          tag: tier.tag,
          blurb: `${tier.blurb} · новый путь`,
          chatRef: chat,
          startsAt,
          fresh: true,
        }))
        made += 1
      }
    }
  }

  // Сортируем: бесплатные и меньший старт выше — удобнее смотреть
  out.sort((a, b) => {
    if (a.free !== b.free) return a.free === '+' ? -1 : 1
    return num(a.startAmount) - num(b.startAmount) || num(a.targetAmount) - num(b.targetAmount)
  })

  return out
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
  const chat = normChat(row.chatRef)
  return (existing || []).some((g) => {
    const gChat = normChat(g.targetChatRef || row.chatRef)
    return (
      Number(g.startAmount) === start
      && Number(g.targetAmount) === target
      && (g.free === '+' ? '+' : '-') === free
      && gChat === chat
    )
  })
}

function isNearExisting(row, existing) {
  if (isDuplicate(row, existing)) return true
  const { paths } = buildOccupied(existing, row.chatRef)
  return isTooSimilar(
    num(row.startAmount),
    num(row.targetAmount),
    row.free,
    row.chatRef,
    paths,
  )
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
 * Полноэкранное окно: предложить только НОВЫЕ → выбрать → подправить → создать.
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
  const [seed, setSeed] = useState(() => Date.now())

  const regenerate = (nextSeed = Date.now(), chat = sharedChat, startsAt = sharedStart) => {
    const pack = buildSuggestedChallenges({
      existing: existingRef.current,
      chatRef: (chat || DEFAULT_CHAT).trim() || DEFAULT_CHAT,
      startsAt: startsAt || '',
      seed: nextSeed,
      limit: 16,
    })
    setRows(pack)
    setSeed(nextSeed)
    setError('')
  }

  useEffect(() => {
    if (!open) return undefined
    setFilter('all')
    setSharedChat(DEFAULT_CHAT)
    setSharedStart('')
    setSaving(false)
    regenerate(Date.now(), DEFAULT_CHAT, '')
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      const next = { ...row, ...patch }
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
    const chat = sharedChat.trim() || DEFAULT_CHAT
    setRows((list) => list.map((row) => ({
      ...row,
      chatRef: chat,
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
    // Доп. защита: внутри пакета тоже не должно быть одинаковых
    const seen = new Set()
    const payload = []
    for (const row of selectedValid) {
      const key = sigKey(row.startAmount, row.targetAmount, row.free, row.chatRef)
      if (seen.has(key)) continue
      if (isDuplicate(row, existing)) continue
      seen.add(key)
      payload.push({
        startAmount: Number(row.startAmount),
        targetAmount: Number(row.targetAmount),
        rewardAmount: Number(row.rewardAmount),
        maxBet: row.free === '+' || row.maxBet === '' ? null : Number(row.maxBet),
        maxUsers: row.maxUsers === '' ? null : Number(row.maxUsers),
        free: row.free === '+' ? '+' : '-',
        chatRef: (row.chatRef || DEFAULT_CHAT).trim() || DEFAULT_CHAT,
        startsAt: row.startsAt ? new Date(row.startsAt).toISOString() : null,
      })
    }
    if (!payload.length) {
      setError('Нет новых заданий для создания. Нажми «Другие предложения».')
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
            <p className="bq-kicker">Только новые пути</p>
            <h3 id={titleId}>Создание челленджей автоматически</h3>
            <p className="bq-auto-lead">
              Подбор смотрит на уже существующие задания и предлагает только свободные пути:
              другой старт/цель, награда ~2–3% от пути, ставка и слоты. Дубликаты и почти копии не показываются.
            </p>
          </div>
          <div className="bq-auto-head-actions">
            <button
              type="button"
              className="bq-btn bq-btn-ghost"
              disabled={saving}
              onClick={() => regenerate(Date.now() + seed)}
            >
              Другие предложения
            </button>
            <button type="button" className="bq-btn bq-btn-ghost" disabled={saving} onClick={onClose}>
              Закрыть
            </button>
          </div>
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
          <button
            type="button"
            className="bq-btn bq-btn-ghost"
            disabled={saving}
            onClick={() => regenerate(Date.now() + seed, sharedChat, sharedStart)}
          >
            Обновить под чат
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
            <button type="button" className="bq-link" onClick={recalcSelected}>Пересчитать награды</button>
            <span>{rows.length} новых · выбрано {selected.length} · к созданию {selectedValid.length}</span>
          </div>
        </div>

        <div className="bq-auto-body">
          {visible.length === 0 ? (
            <div className="bq-empty">
              <strong>Свободных путей в этой зоне почти не осталось</strong>
              <p>Нажми «Другие предложения» или смени чат — подберём другую лестницу.</p>
            </div>
          ) : visible.map((row, idx) => {
            const err = validateRow(row)
            const dup = isDuplicate(row, existing)
            const near = !dup && isNearExisting(row, existing)
            const pct = rewardPct(row)
            const gap = gapOf(row)
            return (
              <article
                key={row.key}
                className={`bq-auto-card${row.selected ? ' is-selected' : ''}${dup || near ? ' is-dup' : ''}${err ? ' is-bad' : ''}`}
                style={{ '--i': idx % 10 }}
              >
                <label className="bq-auto-check">
                  <input
                    type="checkbox"
                    checked={row.selected && !dup}
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
                    {row.fresh && !dup && !near && <span className="bq-auto-flag is-new">Новый</span>}
                    {dup && <span className="bq-auto-flag is-err">Уже существует</span>}
                    {near && <span className="bq-auto-flag">Слишком похож</span>}
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
                        onChange={(e) => patchRow(row.key, { startAmount: e.target.value, fresh: false }, { touchReward: true, touchLimits: true })}
                      />
                    </label>
                    <label className="bq-field">
                      <span>Цель</span>
                      <input
                        className="bq-input"
                        inputMode="numeric"
                        value={row.targetAmount}
                        onChange={(e) => patchRow(row.key, { targetAmount: e.target.value, fresh: false }, { touchReward: true, touchLimits: true })}
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
                          { free: e.target.value === '+' ? '+' : '-', fresh: false },
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
                В списке только свободные пути относительно текущих челленджей.
                Если нужно ещё — жми «Другие предложения».
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
