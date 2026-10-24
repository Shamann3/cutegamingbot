import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  fetchFlame,
  saveFlameGiftDrops,
  saveFlameRewards,
  saveFlameSettings,
  saveFlameSteps,
  saveFlameTitles,
  saveFlameWarmRewards,
} from '../../lib/adminClient'
import DarkPick from '../../components/DarkPick'
import DexItemSearchPicker from '../../components/DexItemSearchPicker'
import '../../styles/flame.css'
import FlameAsk, { ASK } from './FlameAsk'

const KIND_OPTIONS = [
  { value: 'bonus', label: 'Обычный бонус' },
  { value: 'bonus_x2', label: 'Бонус ×2' },
  { value: 'kuty', label: 'Куты' },
  { value: 'item', label: 'Предмет' },
]

const TABS = [
  { id: 'norm', label: 'Норма', hint: 'Сколько писать' },
  { id: 'rewards', label: 'Награды', hint: 'Что дадут за дни' },
  { id: 'warm', label: 'Тёплый час', hint: 'Случайный час' },
  { id: 'status', label: 'Статусы', hint: 'Строка в профиле' },
  { id: 'gift', label: 'Бонус +', hint: '🎁 · клетки 3×3' },
  { id: 'restore', label: 'Вернуть', hint: 'Куты или предмет' },
  { id: 'live', label: 'Живое', hint: 'Серии и награды' },
]

const DEFAULT_BOARD_CELLS = [
  { id: '5321218545621706269', alt: '🎈' },
  { id: '5316569385257702225', alt: '🎒' },
  { id: '5355073951749927916', alt: '🍭' },
  { id: '5285257694985352512', alt: '💍' },
  { id: '5438458242130806642', alt: '🎁' },
  { id: '5310214083495103551', alt: '🎁' },
  { id: '5424987025667293801', alt: '🐰' },
  { id: '5427103061564752778', alt: '🐰' },
  { id: '5424861140175849850', alt: '🎂' },
]

function cleanCellAlt(raw) {
  const text = String(raw || '').replace(/<[^>]+>/g, '').replace(/[<>]/g, '').trim()
  return (text || '🎁').slice(0, 8)
}

function parseCellPaste(text) {
  const src = String(text || '').trim()
  if (!src) return []
  const tagged = []
  const tag = /<tg-emoji\b[^>]*emoji-id\s*=\s*['"](\d{5,32})['"][^>]*>([\s\S]*?)<\/tg-emoji>/gi
  for (const match of src.matchAll(tag)) {
    tagged.push({ id: match[1], alt: cleanCellAlt(match[2]) })
  }
  if (tagged.length) return tagged.slice(0, 9)
  if (/^\d{5,32}$/.test(src)) return [{ id: src, alt: '🎁' }]
  if (/^[\d\s,;]+$/.test(src)) {
    return (src.match(/\d{5,32}/g) || []).slice(0, 9).map((id) => ({ id, alt: '🎁' }))
  }
  return []
}

function boardCellsFrom(raw) {
  const items = Array.isArray(raw) ? raw : []
  return DEFAULT_BOARD_CELLS.map((fallback, index) => {
    const piece = items[index]
    const id = String(piece?.id || '').trim()
    if (/^\d{5,32}$/.test(id)) return { id, alt: cleanCellAlt(piece?.alt) }
    return { id: fallback.id, alt: fallback.alt }
  })
}

function CellBoard({ cells, onChange }) {
  const ready = boardCellsFrom(cells)
  const [picked, setPicked] = useState(0)
  const [draft, setDraft] = useState('')
  const [hint, setHint] = useState('')
  const fieldRef = useRef(null)
  const sameAsDefault = ready.every((cell, index) => (
    cell.id === DEFAULT_BOARD_CELLS[index].id && cell.alt === DEFAULT_BOARD_CELLS[index].alt
  ))

  const choose = (index) => {
    setPicked(index)
    setDraft('')
    setHint('')
    requestAnimationFrame(() => fieldRef.current?.focus())
  }

  const applyText = (text) => {
    const found = parseCellPaste(text)
    if (!found.length) {
      setHint('Не разобрали. Нужен id или тег tg-emoji.')
      return
    }
    const fromTag = /<tg-emoji/i.test(text)
    const next = ready.map((cell) => ({ ...cell }))
    let placed = 0
    found.forEach((cell, offset) => {
      const index = picked + offset
      if (index < 9) {
        next[index] = {
          id: cell.id,
          alt: fromTag ? cell.alt : (next[index].alt || cell.alt),
        }
        placed += 1
      }
    })
    onChange(next)
    setDraft('')
    setHint(placed > 1 ? `Вставили ${placed} подряд.` : `Клетка ${picked + 1} обновлена.`)
    setPicked(Math.min(8, picked + placed))
  }

  return (
    <div className="flame-cells">
      <div className="flame-card-head">
        <h3>Клетки 3×3</h3>
        <button
          type="button"
          className="sec-btn sec-btn-ghost"
          disabled={sameAsDefault}
          onClick={() => {
            onChange(DEFAULT_BOARD_CELLS.map((cell) => ({ ...cell })))
            setHint('Снова обычные клетки.')
            setDraft('')
          }}
        >
          Обычные
        </button>
      </div>
      <p className="flame-note">
        Нажмите клетку и вставьте премиум-эмодзи. Порядок тот же, что у игрока: слева направо, сверху вниз.
        В панели виден запасной знак, в Telegram на кнопке — сам премиум-эмодзи.
      </p>
      <div className="flame-cell-grid" role="group" aria-label="Клетки бонуса">
        {ready.map((cell, index) => (
          <button
            key={`cell-${index}`}
            type="button"
            className={index === picked ? 'flame-cell is-on' : 'flame-cell'}
            aria-pressed={index === picked}
            title={cell.id}
            onClick={() => choose(index)}
          >
            <strong>{cell.alt}</strong>
            <small>{index + 1} · …{String(cell.id).slice(-4)}</small>
          </button>
        ))}
      </div>
      <label className="flame-field">
        <span>Клетка {picked + 1}</span>
        <input
          ref={fieldRef}
          value={draft}
          placeholder="id или <tg-emoji emoji-id='…'>🎁</tg-emoji>"
          onChange={(e) => {
            setDraft(e.target.value)
            if (hint) setHint('')
          }}
          onPaste={(e) => {
            const text = e.clipboardData?.getData('text') || ''
            if (!text.trim()) return
            e.preventDefault()
            applyText(text)
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              applyText(draft)
            }
          }}
        />
        <FlameAsk {...ASK.cellPaste} />
      </label>
      <div className="flame-cell-actions">
        <button type="button" className="sec-btn" onClick={() => applyText(draft)}>
          Вставить в клетку
        </button>
        <p className="flame-note">
          {hint || 'Несколько тегов подряд заполнят клетки дальше. Сохраняется кнопкой «Сохранить Бонус +».'}
        </p>
      </div>
    </div>
  )
}

function FlameSwitch({ checked, onChange, children }) {
  return (
    <label className="flame-switch">
      <input type="checkbox" checked={Boolean(checked)} onChange={onChange} />
      <span className="flame-knob" aria-hidden="true" />
      <span>{children}</span>
    </label>
  )
}

function FlameFold({ open, children }) {
  return (
    <div className={open ? 'flame-fold is-open' : 'flame-fold'}>
      <div className="flame-fold-inner">
        {children}
      </div>
    </div>
  )
}

function giftWords(row) {
  if (row.kind === 'kuty') return `${Math.max(1, Number(row.amount) || 1)} кут`
  if (row.kind === 'item') {
    const name = String(row.itemName || '').trim() || 'предмет'
    const n = Math.max(1, Number(row.amount) || 1)
    return n === 1 ? name : `${name} ×${n}`
  }
  if (row.kind === 'bonus_x2') {
    const n = Math.max(1, Number(row.amount) || 1)
    return n === 1 ? 'бонус ×2' : `бонус ×2 ×${n}`
  }
  if (row.kind === 'bonus') {
    const n = Math.max(1, Number(row.amount) || 1)
    return n === 1 ? 'обычный бонус' : `обычный бонус ×${n}`
  }
  return kindLabel(row.kind)
}

function groupRewardDays(rows) {
  const order = []
  const map = new Map()
  rows.forEach((row, index) => {
    const key = String(row.day ?? '').trim() === '' ? `__empty_${index}` : String(row.day)
    if (!map.has(key)) {
      map.set(key, { key, day: row.day, gifts: [] })
      order.push(key)
    }
    map.get(key).gifts.push({ ...row, _index: index })
  })
  return order.map((key) => map.get(key))
}

function digits(value) {
  return String(value ?? '').replace(/[^\d]/g, '')
}

function kindLabel(kind) {
  return KIND_OPTIONS.find((row) => row.value === kind)?.label || 'Награда'
}

function catalogFace(catalog, name) {
  const raw = String(name || '').trim()
  if (!raw) return null
  return (catalog || []).find((row) => row.name === raw || row.name1 === raw) || null
}

function namedDrops(rows) {
  const seen = new Set()
  const out = []
  for (const row of rows || []) {
    const name = String(row.itemName || '').trim()
    if (!name || seen.has(name)) continue
    if (row.kind && row.kind !== 'item') continue
    seen.add(name)
    out.push(row)
  }
  return out
}

function FlameItemPick({ value, onChange, label = 'Предмет', emptyLabel = 'Выберите предмет', catalog = [], ask = null }) {
  return (
    <div className="flame-item-pick">
      <DexItemSearchPicker
        label={label}
        value={value || ''}
        onChange={onChange}
        valueMode="name"
        catalog={catalog}
        compact
        clearable
        emptyLabel={emptyLabel}
        placeholder="Название или эмодзи…"
        hint="Каталог предметов. Ищите по эмодзи, названию, коду или id."
      />
      {ask ? <FlameAsk {...ask} /> : null}
    </div>
  )
}

function sourceLabel(source) {
  if (source === 'warm') return 'тёплый час'
  if (source === 'gift') return '🎁'
  if (source === 'streak') return 'день серии'
  return source || 'награда'
}

export default function FlameSection() {
  const [tab, setTab] = useState('norm')
  const [board, setBoard] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const [form, setForm] = useState({})
  const [steps, setSteps] = useState([])
  const [rewards, setRewards] = useState([])
  const [titles, setTitles] = useState([])
  const [warmRewards, setWarmRewards] = useState([])
  const [giftDrops, setGiftDrops] = useState([])

  const apply = useCallback((data) => {
    setBoard(data)
    const s = data?.settings || {}
    setForm({
      enabled: Boolean(s.enabled),
      baseMessages: String(s.base_messages || 200),
      warmEnabled: Boolean(s.warm_enabled),
      warmMinDay: String(s.warm_min_day || 3),
      warmEvery: String(s.warm_every || 40),
      warmCap: String(s.warm_cap || 3),
      warmFrom: String(s.warm_from ?? 15),
      warmTo: String(s.warm_to ?? 24),
      statusEnabled: s.status_enabled !== false,
      profitEnabled: s.profit_enabled !== false,
      profitHour: String(s.profit_hour ?? 21),
      minWords: String(s.min_words || 2),
      blockDup: s.block_dup !== false,
      giftEnabled: s.gift_enabled !== false,
      giftMult: String(s.gift_mult || 1),
      giftKutyMin: String(s.gift_kuty_min || 1),
      giftKutyMax: String(s.gift_kuty_max || 3),
      giftExtraKutyOn: s.gift_extra_kuty_on !== false,
      giftExtraKutyChance: String(s.gift_extra_kuty_chance ?? 35),
      giftExtraKutyMin: String(s.gift_extra_kuty_min ?? 5),
      giftExtraKutyMax: String(s.gift_extra_kuty_max ?? 25),
      giftItemOn: s.gift_item_on !== false,
      giftItemChance: String(s.gift_item_chance ?? 40),
      giftItemCount: String(s.gift_item_count ?? 1),
      giftFallbackPct: String(s.gift_fallback_pct ?? 30),
      restoreEnabled: s.restore_enabled !== false,
      restoreDays: String(s.restore_days || 3),
      restoreKuty: String(s.restore_kuty ?? 500),
      restoreItem: s.restore_item || '',
      restoreItemCount: String(s.restore_item_count || 1),
      giftCellEmojis: boardCellsFrom(data?.gift?.cell_emojis),
    })
    setSteps((data?.steps || []).map((row) => ({
      fromDay: String(row.from_day),
      messages: String(row.messages),
    })))
    setRewards((data?.rewards || []).map((row) => ({
      day: String(row.day),
      kind: row.kind,
      amount: String(row.amount || 1),
      itemName: row.item_name || '',
    })))
    setTitles((data?.titles || []).map((row) => ({
      fromDay: String(row.from_day),
      title: row.title || '',
      emojiId: row.emoji_id || '',
    })))
    setWarmRewards((data?.warm?.rewards || []).map((row) => ({
      kind: row.kind,
      amount: String(row.amount || 1),
      itemName: row.item_name || '',
      weight: String(row.weight || 1),
    })))
    setGiftDrops((data?.gift?.drops || []).map((row) => ({
      kind: row.kind,
      amountMin: String(row.amount_min || 1),
      amountMax: String(row.amount_max || 1),
      itemName: row.item_name || '',
      weight: String(row.weight || 1),
      showPreview: Boolean(row.show_preview),
    })))
  }, [])

  const load = useCallback(async () => {
    try {
      apply(await fetchFlame())
      setError('')
    } catch (err) {
      setError(err?.message || 'Не удалось открыть огонёк')
    }
  }, [apply])

  useEffect(() => { load() }, [load])

  const run = async (key, job) => {
    setBusy(key)
    setError('')
    try {
      apply(await job())
    } catch (err) {
      setError(err?.message || 'Не сохранилось')
    } finally {
      setBusy('')
    }
  }

  const patch = (key, value) => setForm((prev) => ({ ...prev, [key]: value }))

  const bonusItems = useMemo(() => namedDrops(giftDrops), [giftDrops])
  const bonusChance = Math.max(0, Math.min(100, Number(form.giftItemChance) || 0))
  const bonusSlots = Math.max(1, Math.min(5, Number(form.giftItemCount) || 1))
  const bonusCover = Math.min(5, bonusItems.length)
  const bonusGivesAll = bonusItems.length > 0 && bonusSlots >= bonusCover && bonusChance >= 100
  const bonusGive = Math.min(bonusSlots, bonusItems.length, 5)
  const bonusDropLine = bonusItems.length === 0
    ? 'Сначала отметьте предметы. Без них в открытии останутся только куты.'
    : bonusChance < 1
      ? `Выбрано ${bonusItems.length}. Шанс 0% — эти предметы не выпадут.`
      : `Выбрано ${bonusItems.length}. За одно открытие выпадет до ${bonusGive} разных.${bonusChance >= 100 ? '' : ` Шанс каждого слота — ${bonusChance}%.`}${bonusItems.length > 5 ? ' Больше пяти разных за раз выдать нельзя.' : ''}`

  const addBonusItem = (name) => {
    const clean = String(name || '').trim()
    if (!clean) return
    const have = bonusItems.length
    if (bonusItems.some((row) => String(row.itemName || '').trim() === clean)) return
    setGiftDrops((rows) => [
      ...rows,
      { kind: 'item', amountMin: '1', amountMax: '1', itemName: clean, weight: '1', showPreview: true },
    ])
    setForm((prev) => {
      const current = Math.max(1, Math.min(5, Number(prev.giftItemCount) || 1))
      if (have > 0 && current >= have) {
        return { ...prev, giftItemCount: String(Math.min(5, have + 1)) }
      }
      return prev
    })
  }

  const removeBonusItem = (name) => {
    const clean = String(name || '').trim()
    setGiftDrops((rows) => rows.filter((row) => String(row.itemName || '').trim() !== clean))
  }

  const patchBonusItem = (name, next) => {
    const clean = String(name || '').trim()
    setGiftDrops((rows) => rows.map((row) => (
      String(row.itemName || '').trim() === clean ? { ...row, ...next, kind: 'item' } : row
    )))
  }

  const settingsPayload = () => ({
    enabled: form.enabled,
    baseMessages: Math.max(1, Number(form.baseMessages) || 1),
    warmEnabled: form.warmEnabled,
    warmMinDay: Math.max(1, Number(form.warmMinDay) || 1),
    warmEvery: Math.max(1, Number(form.warmEvery) || 1),
    warmCap: Math.max(1, Number(form.warmCap) || 1),
    warmFrom: Math.max(0, Math.min(23, Number(form.warmFrom) || 0)),
    warmTo: Math.max(1, Math.min(24, Number(form.warmTo) || 24)),
    statusEnabled: form.statusEnabled,
    profitEnabled: form.profitEnabled,
    profitHour: Math.max(0, Math.min(23, Number(form.profitHour) || 0)),
    minWords: Math.max(1, Number(form.minWords) || 2),
    blockDup: form.blockDup,
    giftEnabled: form.giftEnabled,
    giftMult: Math.max(1, Number(form.giftMult) || 1),
    giftKutyMin: Math.max(1, Number(form.giftKutyMin) || 1),
    giftKutyMax: Math.max(1, Number(form.giftKutyMax) || 1),
    giftExtraKutyOn: Boolean(form.giftExtraKutyOn),
    giftExtraKutyChance: Math.max(0, Math.min(100, Number(form.giftExtraKutyChance) || 0)),
    giftExtraKutyMin: Math.max(0, Number(form.giftExtraKutyMin) || 0),
    giftExtraKutyMax: Math.max(0, Number(form.giftExtraKutyMax) || 0),
    giftItemOn: Boolean(form.giftItemOn),
    giftItemChance: Math.max(0, Math.min(100, Number(form.giftItemChance) || 0)),
    giftItemCount: Math.max(1, Math.min(5, Number(form.giftItemCount) || 1)),
    giftFallbackPct: Math.max(1, Math.min(100, Number(form.giftFallbackPct) || 30)),
    restoreEnabled: Boolean(form.restoreEnabled),
    restoreDays: Math.max(1, Math.min(30, Number(form.restoreDays) || 3)),
    restoreKuty: Math.max(0, Number(form.restoreKuty) || 0),
    restoreItem: String(form.restoreItem || '').trim(),
    restoreItemCount: Math.max(1, Math.min(100, Number(form.restoreItemCount) || 1)),
    giftCellEmojis: boardCellsFrom(form.giftCellEmojis).map((cell) => ({ id: cell.id, alt: cell.alt })),
  })

  const giftDropPayload = () => {
    const seen = new Set()
    const items = []
    const legacy = []
    for (const row of giftDrops) {
      const name = String(row.itemName || '').trim()
      if (!row.kind || row.kind === 'item' || name) {
        if (!name || seen.has(name)) continue
        seen.add(name)
        items.push({
          kind: 'item',
          amountMin: 1,
          amountMax: 1,
          itemName: name,
          weight: Math.max(1, Number(row.weight) || 1),
          showPreview: row.showPreview !== false,
        })
      } else {
        legacy.push({
          kind: row.kind,
          amountMin: Math.max(1, Number(row.amountMin) || 1),
          amountMax: Math.max(1, Number(row.amountMax) || Number(row.amountMin) || 1),
          itemName: '',
          weight: Math.max(1, Number(row.weight) || 1),
          showPreview: false,
        })
      }
    }
    return [...items, ...legacy]
  }

  const saveAllSettings = () => run('settings', () => saveFlameSettings(settingsPayload()))

  const saveBonusPlus = () => run('settings', async () => {
    await saveFlameSettings(settingsPayload())
    return saveFlameGiftDrops({ drops: giftDropPayload() })
  })

  const warmHour = board?.warm?.hour
  const catalog = useMemo(() => {
    const rows = board?.items || []
    if (!rows.length) return []
    if (typeof rows[0] === 'string') {
      return rows.map((name) => ({ id: name, name, name1: '', emoji: '📦', price: 0 }))
    }
    return rows
  }, [board?.items])

  const restoreHint = useMemo(() => {
    if (!form.restoreEnabled) {
      return 'Возврат выключен. На «вернуть огонёк» человек получит ответ, что погасшую серию сейчас вернуть нельзя.'
    }
    const ways = []
    const kuty = Number(form.restoreKuty) || 0
    if (kuty > 0) ways.push(`${kuty} кут`)
    const item = String(form.restoreItem || '').trim()
    const count = Math.max(1, Number(form.restoreItemCount) || 1)
    if (item) ways.push(count === 1 ? item : `${item} ×${count}`)
    const days = Math.max(1, Number(form.restoreDays) || 1)
    if (!ways.length) {
      return 'Возврат включён, но цены нет. Поставьте куты больше нуля или выберите предмет.'
    }
    return `Если человек перестанет продлевать огонёк, «вернуть огонёк» живёт ${days} дн. Серия поднимется на столько дней, сколько сгорело. Цена: ${ways.join(' или ')}. Новая серия сжигает старую. После возврата огонёк снова нужно продлить до 00:00 по Москве.`
  }, [form.restoreEnabled, form.restoreKuty, form.restoreItem, form.restoreItemCount, form.restoreDays])

  const warmHint = useMemo(() => {
    if (warmHour == null) return 'Час выберется сам в заданном окне.'
    const next = (Number(warmHour) + 1) % 24
    return `Сегодня тёплый час: ${String(warmHour).padStart(2, '0')}:00–${String(next).padStart(2, '0')}:00 МСК`
  }, [warmHour])

  const rewardDays = useMemo(() => groupRewardDays(rewards), [rewards])

  const playerReveal = useMemo(() => {
    const mult = Math.max(1, Math.min(10, Number(form.giftMult) || 1))
    const lo = Math.max(1, Number(form.giftKutyMin) || 1) * mult
    const hi = Math.max(lo, (Number(form.giftKutyMax) || lo) * mult)
    const kuty = []
    kuty.push(lo === hi ? `С выбранной клетки: +${lo} кут` : `С выбранной клетки: +${lo}…${hi} кут`)
    if (form.giftExtraKutyOn) {
      const chance = Math.max(0, Math.min(100, Number(form.giftExtraKutyChance) || 0))
      let a = Math.max(0, Number(form.giftExtraKutyMin) || 0)
      let b = Math.max(a, Number(form.giftExtraKutyMax) || 0)
      if (chance >= 1 && b >= 1) {
        a = Math.max(1, a)
        b = Math.max(a, b)
        const bit = a === b ? `+${a} кут` : `+${a}…${b} кут`
        kuty.push(chance >= 100 ? `ещё ${bit} — дополнительно к клетке` : `иногда ещё ${bit} — не в каждом открытии`)
      }
    }
    const shown = form.giftItemOn
      ? giftDrops.filter((row) => row.showPreview && String(row.itemName || '').trim()).map((row) => row.itemName)
      : []
    const hidden = form.giftItemOn
      ? giftDrops
        .filter((row) => !row.showPreview && String(row.itemName || '').trim())
        .map((row) => row.itemName)
      : []
    const unique = (rows) => [...new Set(rows)]
    const shownNames = unique(shown)
    const hiddenNames = unique(hidden).filter((name) => !shownNames.includes(name))
    const slots = shownNames.length
      ? Math.min(Math.max(1, Math.min(5, Number(form.giftItemCount) || 1)), shownNames.length)
      : 0
    return { kuty, shownNames, hiddenNames, slots, enabled: Boolean(form.giftEnabled) }
  }, [
    form.giftEnabled,
    form.giftMult,
    form.giftKutyMin,
    form.giftKutyMax,
    form.giftExtraKutyOn,
    form.giftExtraKutyChance,
    form.giftExtraKutyMin,
    form.giftExtraKutyMax,
    form.giftItemOn,
    form.giftItemCount,
    giftDrops,
  ])

  const patchReward = (index, patch) => {
    setRewards((rows) => rows.map((item, i) => (i === index ? { ...item, ...patch } : item)))
  }

  const setDayForPack = (pack, value) => {
    const indexes = new Set(pack.gifts.map((g) => g._index))
    setRewards((rows) => rows.map((item, i) => (indexes.has(i) ? { ...item, day: value } : item)))
  }

  const addDayPack = () => {
    const last = rewards.reduce((max, row) => Math.max(max, Number(row.day) || 0), 0)
    setRewards((rows) => [...rows, { day: String(last + 1 || 1), kind: 'kuty', amount: '10', itemName: '' }])
  }

  const addGiftToPack = (pack) => {
    setRewards((rows) => [...rows, {
      day: pack.day || '',
      kind: 'item',
      amount: '1',
      itemName: '',
    }])
  }

  const removePack = (pack) => {
    const indexes = new Set(pack.gifts.map((g) => g._index))
    setRewards((rows) => rows.filter((_, i) => !indexes.has(i)))
  }

  return (
    <section className="flame-page">
      <header className="flame-hero">
        <span className="flame-orb" aria-hidden="true" />
        <div>
          <h2>Огонёк</h2>
          <p>Серия дней в чате. Награды за дни, тёплый час, статус в профиле и Бонус +.</p>
        </div>
      </header>

      {error && <p className="flame-error" role="alert">{error}</p>}
      {!board && !error && <p className="staff-hint">Открываем огонёк…</p>}

      {board && (
        <>
          <div className="flame-stats">
            <article>
              <strong>{board.alive || 0}</strong>
              <span>живых серий</span>
            </article>
            <article>
              <strong>{board.keptToday || 0}</strong>
              <span>закрыли сегодня</span>
            </article>
            {form.warmEnabled && (
              <article>
                <strong>{warmHour == null ? '—' : `${String(warmHour).padStart(2, '0')}:00`}</strong>
                <span>тёплый час</span>
              </article>
            )}
          </div>

          <div className="flame-work">
          <nav className="flame-tabs" aria-label="Разделы огонька">
            {TABS.map((row) => (
              <button
                key={row.id}
                type="button"
                className={`flame-tab${tab === row.id ? ' is-on' : ''}`}
                onClick={() => setTab(row.id)}
                aria-current={tab === row.id ? 'page' : undefined}
              >
                <span>{row.label}</span>
                <small>{row.hint}</small>
              </button>
            ))}
          </nav>
          <div className="flame-pane" key={tab}>

          {tab === 'norm' && (
            <section className="flame-card">
              <div className="flame-card-head">
                <h3>Норма и защита</h3>
                <div className="flame-ask-slot">
                  <FlameSwitch checked={form.enabled} onChange={(e) => patch('enabled', e.target.checked)}>
                    {form.enabled ? 'Огонёк включён' : 'Огонёк выключен'}
                  </FlameSwitch>
                  <FlameAsk {...ASK.enabled} />
                </div>
              </div>
              <FlameFold open={Boolean(form.enabled)}>
                <div className="flame-grid-2">
                  <label className="flame-field">
                    <span>Сообщений в первый день</span>
                    <input inputMode="numeric" value={form.baseMessages} onChange={(e) => patch('baseMessages', digits(e.target.value))} />
                    <FlameAsk {...ASK.baseMessages} />
                  </label>
                  <label className="flame-field">
                    <span>Минимум слов в сообщении</span>
                    <input inputMode="numeric" value={form.minWords} onChange={(e) => patch('minWords', digits(e.target.value))} />
                    <FlameAsk {...ASK.minWords} />
                  </label>
                </div>
                <div className="flame-ask-slot">
                  <FlameSwitch checked={form.blockDup} onChange={(e) => patch('blockDup', e.target.checked)}>
                    Не считать одинаковый текст подряд
                  </FlameSwitch>
                  <FlameAsk {...ASK.blockDup} />
                </div>
                <div className="flame-ask-slot">
                  <FlameSwitch checked={form.profitEnabled} onChange={(e) => patch('profitEnabled', e.target.checked)}>
                    Вечерняя карточка профита в личку
                  </FlameSwitch>
                  <FlameAsk {...ASK.profit} />
                </div>
                <FlameFold open={Boolean(form.profitEnabled)}>
                  <label className="flame-field">
                    <span>Час карточки (МСК)</span>
                    <input inputMode="numeric" value={form.profitHour} onChange={(e) => patch('profitHour', digits(e.target.value))} />
                    <FlameAsk {...ASK.profitHour} />
                  </label>
                </FlameFold>
                <p className="flame-note">
                  В счёт идут живые сообщения в официальных группах. Команды, игры и одно и то же сообщение подряд не считаются. Как только за сутки по Москве норма набрана, огонёк сразу становится на день длиннее. Если до 00:00 нормы нет — гаснет.
                </p>
                <div className="flame-card-head">
                  <h3>Рост нормы</h3>
                  <button type="button" className="sec-btn sec-btn-ghost" onClick={() => setSteps((rows) => [...rows, { fromDay: '', messages: '' }])}>
                    Добавить день
                  </button>
                </div>
                <ul className="flame-rows">
                  {steps.map((row, index) => (
                    <li key={`step-${index}`}>
                      <label>
                        <span>С дня</span>
                        <input inputMode="numeric" value={row.fromDay} onChange={(e) => {
                          const value = digits(e.target.value)
                          setSteps((rows) => rows.map((item, i) => i === index ? { ...item, fromDay: value } : item))
                        }} />
                        <FlameAsk {...ASK.stepFrom} />
                      </label>
                      <label>
                        <span>Сообщений</span>
                        <input inputMode="numeric" value={row.messages} onChange={(e) => {
                          const value = digits(e.target.value)
                          setSteps((rows) => rows.map((item, i) => i === index ? { ...item, messages: value } : item))
                        }} />
                        <FlameAsk {...ASK.stepMessages} />
                      </label>
                      <button type="button" className="sec-btn sec-btn-ghost flame-drop" onClick={() => setSteps((rows) => rows.filter((_, i) => i !== index))}>Убрать</button>
                    </li>
                  ))}
                </ul>
                <div className="flame-actions">
                  <button
                    type="button"
                    className="sec-btn"
                    disabled={busy === 'steps'}
                    onClick={() => run('steps', () => saveFlameSteps({
                      steps: steps
                        .map((row) => ({ fromDay: Number(row.fromDay), messages: Number(row.messages) }))
                        .filter((row) => row.fromDay >= 1 && row.messages >= 1),
                    }))}
                  >
                    {busy === 'steps' ? 'Сохраняем…' : 'Сохранить ступени'}
                  </button>
                </div>
              </FlameFold>
              <div className="flame-actions">
                <button type="button" className="sec-btn" disabled={busy === 'settings'} onClick={saveAllSettings}>
                  {busy === 'settings' ? 'Сохраняем…' : 'Сохранить настройки'}
                </button>
              </div>
            </section>
          )}

          {tab === 'rewards' && (
            <section className="flame-card">
              <div className="flame-card-head">
                <h3>Награды за дни серии</h3>
                <button type="button" className="sec-btn sec-btn-ghost" onClick={addDayPack}>
                  Добавить день
                </button>
              </div>
              <p className="flame-note">
                Один день серии = один пакет. В пакет можно положить несколько подарков: все придут в личку сразу, в момент, когда серия доходит до этого дня. Куты и предметы берутся из техгрупп, магазина или биржи.
              </p>
              {rewardDays.length === 0 && (
                <p className="flame-empty">Пока пусто. Добавьте день — люди увидят награды в справке первыми.</p>
              )}
              <div className="flame-day-list">
                {rewardDays.map((pack) => {
                  const summary = pack.gifts.map(giftWords).filter(Boolean).join(' · ')
                  return (
                    <article key={pack.key} className="flame-day-pack">
                      <div className="flame-day-pack-head">
                        <label className="flame-field flame-day-num">
                          <span>День серии</span>
                          <input
                            inputMode="numeric"
                            value={pack.day}
                            onChange={(e) => setDayForPack(pack, digits(e.target.value))}
                          />
                          <FlameAsk {...ASK.rewardDay} />
                        </label>
                        <div className="flame-actions">
                          <button type="button" className="sec-btn sec-btn-ghost" onClick={() => addGiftToPack(pack)}>
                            + подарок
                          </button>
                          <button type="button" className="sec-btn sec-btn-ghost" onClick={() => removePack(pack)}>
                            Убрать день
                          </button>
                        </div>
                      </div>
                      {summary && (
                        <p className="flame-consequence">
                          Получат: <b>{summary}</b>
                        </p>
                      )}
                      <ul className="flame-rows is-reward">
                        {pack.gifts.map((row) => (
                          <li key={`reward-${row._index}`}>
                            <div className="flame-ask-slot">
                              <DarkPick
                                label="Что дать"
                                value={row.kind}
                                options={KIND_OPTIONS}
                                searchable={false}
                                onChange={(kind) => patchReward(row._index, { kind })}
                              />
                              <FlameAsk {...ASK.rewardKind} />
                            </div>
                            <label>
                              <span>{row.kind === 'item' ? 'Штук' : row.kind === 'kuty' ? 'Кут' : 'Раз'}</span>
                              <input
                                inputMode="numeric"
                                value={row.amount}
                                onChange={(e) => patchReward(row._index, { amount: digits(e.target.value) })}
                              />
                              <FlameAsk {...ASK.rewardAmount} />
                            </label>
                            {row.kind === 'item' && (
                              <div className="is-wide">
                                <FlameItemPick
                                  catalog={catalog}
                                  value={row.itemName}
                                  ask={ASK.rewardItem}
                                  onChange={(itemName) => patchReward(row._index, { itemName })}
                                />
                              </div>
                            )}
                            <button
                              type="button"
                              className="sec-btn sec-btn-ghost flame-drop"
                              aria-label={`Убрать ${kindLabel(row.kind)}`}
                              onClick={() => setRewards((rows) => rows.filter((_, i) => i !== row._index))}
                            >
                              Убрать
                            </button>
                          </li>
                        ))}
                      </ul>
                    </article>
                  )
                })}
              </div>
              <button
                type="button"
                className="sec-btn"
                disabled={busy === 'rewards'}
                onClick={() => run('rewards', () => saveFlameRewards({
                  rewards: rewards
                    .map((row) => ({
                      day: Number(row.day),
                      kind: row.kind,
                      amount: Math.max(1, Number(row.amount) || 1),
                      itemName: row.kind === 'item' ? row.itemName : '',
                    }))
                    .filter((row) => row.day >= 1 && row.kind && (row.kind !== 'item' || row.itemName)),
                }))}
              >
                {busy === 'rewards' ? 'Сохраняем…' : 'Сохранить награды'}
              </button>
            </section>
          )}

          {tab === 'warm' && (
            <section className="flame-card">
              <div className="flame-card-head">
                <h3>Тёплый час</h3>
                <div className="flame-ask-slot">
                  <FlameSwitch checked={form.warmEnabled} onChange={(e) => patch('warmEnabled', e.target.checked)}>
                    {form.warmEnabled ? 'Включён' : 'Выключен'}
                  </FlameSwitch>
                  <FlameAsk {...ASK.warm} />
                </div>
              </div>
              <FlameFold open={Boolean(form.warmEnabled)}>
              <p className="flame-note">{warmHint}. Каждый день в заданном окне выбирается один час.</p>
              <div className="flame-grid-2">
                <label className="flame-field">
                  <span>С какого дня серии</span>
                  <input inputMode="numeric" value={form.warmMinDay} onChange={(e) => patch('warmMinDay', digits(e.target.value))} />
                  <FlameAsk {...ASK.warmMinDay} />
                </label>
                <label className="flame-field">
                  <span>Каждые N сообщений</span>
                  <input inputMode="numeric" value={form.warmEvery} onChange={(e) => patch('warmEvery', digits(e.target.value))} />
                  <FlameAsk {...ASK.warmEvery} />
                </label>
                <label className="flame-field">
                  <span>Макс. наград за день</span>
                  <input inputMode="numeric" value={form.warmCap} onChange={(e) => patch('warmCap', digits(e.target.value))} />
                  <FlameAsk {...ASK.warmCap} />
                </label>
              </div>
              <div className="flame-card-head">
                <h3>Что может выпасть</h3>
                <button type="button" className="sec-btn sec-btn-ghost" onClick={() => setWarmRewards((rows) => [...rows, { kind: 'kuty', amount: '10', itemName: '', weight: '1' }])}>
                  Добавить
                </button>
              </div>
              <ul className="flame-rows is-warm">
                {warmRewards.map((row, index) => (
                  <li key={`warm-${index}`}>
                    <div className="flame-ask-slot">
                      <DarkPick
                        label="Что"
                        value={row.kind}
                        options={KIND_OPTIONS}
                        searchable={false}
                        onChange={(kind) => setWarmRewards((rows) => rows.map((item, i) => i === index ? { ...item, kind } : item))}
                      />
                      <FlameAsk {...ASK.warmKind} />
                    </div>
                    <label>
                      <span>Сколько</span>
                      <input inputMode="numeric" value={row.amount} onChange={(e) => {
                        const value = digits(e.target.value)
                        setWarmRewards((rows) => rows.map((item, i) => i === index ? { ...item, amount: value } : item))
                      }} />
                      <FlameAsk {...ASK.warmAmount} />
                    </label>
                    <label>
                      <span>Вес</span>
                      <input inputMode="numeric" value={row.weight} onChange={(e) => {
                        const value = digits(e.target.value)
                        setWarmRewards((rows) => rows.map((item, i) => i === index ? { ...item, weight: value } : item))
                      }} />
                      <FlameAsk {...ASK.warmWeight} />
                    </label>
                    {row.kind === 'item' && (
                      <div className="is-wide">
                        <FlameItemPick
                          catalog={catalog}
                          value={row.itemName}
                          ask={ASK.warmItem}
                          onChange={(itemName) => setWarmRewards((rows) => rows.map((item, i) => i === index ? { ...item, itemName } : item))}
                        />
                      </div>
                    )}
                    <button type="button" className="sec-btn sec-btn-ghost flame-drop" onClick={() => setWarmRewards((rows) => rows.filter((_, i) => i !== index))}>Убрать</button>
                  </li>
                ))}
                </ul>
                <div className="flame-actions">
                  <button
                    type="button"
                    className="sec-btn"
                    disabled={busy === 'warm'}
                    onClick={() => run('warm', () => saveFlameWarmRewards({
                      rewards: warmRewards
                        .map((row) => ({
                          kind: row.kind,
                          amount: Math.max(1, Number(row.amount) || 1),
                          itemName: row.kind === 'item' ? row.itemName : '',
                          weight: Math.max(1, Number(row.weight) || 1),
                        }))
                        .filter((row) => row.kind && (row.kind !== 'item' || row.itemName)),
                    }))}
                  >
                    {busy === 'warm' ? 'Сохраняем…' : 'Сохранить награды часа'}
                  </button>
                </div>
              </FlameFold>
              <div className="flame-actions">
                <button type="button" className="sec-btn" disabled={busy === 'settings'} onClick={saveAllSettings}>
                  Сохранить час
                </button>
              </div>
            </section>
          )}

          {tab === 'status' && (
            <section className="flame-card">
              <div className="flame-card-head">
                <h3>Статусы огонька</h3>
                <div className="flame-ask-slot">
                  <FlameSwitch checked={form.statusEnabled} onChange={(e) => patch('statusEnabled', e.target.checked)}>
                    {form.statusEnabled ? 'В профиле видны' : 'Скрыты'}
                  </FlameSwitch>
                  <FlameAsk {...ASK.status} />
                </div>
              </div>
              <FlameFold open={Boolean(form.statusEnabled)}>
              <p className="flame-note">Короткий титул в профиле и в топе. Пример: «Искра», «Живой огонь», «Негасимый».</p>
              <button type="button" className="sec-btn sec-btn-ghost" onClick={() => setTitles((rows) => [...rows, { fromDay: '', title: '', emojiId: '' }])}>
                Добавить статус
              </button>
              <ul className="flame-rows is-title">
                {titles.map((row, index) => (
                  <li key={`title-${index}`}>
                    <label>
                      <span>С дня</span>
                      <input inputMode="numeric" value={row.fromDay} onChange={(e) => {
                        const value = digits(e.target.value)
                        setTitles((rows) => rows.map((item, i) => i === index ? { ...item, fromDay: value } : item))
                      }} />
                      <FlameAsk {...ASK.titleFrom} />
                    </label>
                    <label className="is-wide">
                      <span>Название</span>
                      <input value={row.title} maxLength={60} onChange={(e) => {
                        const title = e.target.value
                        setTitles((rows) => rows.map((item, i) => i === index ? { ...item, title } : item))
                      }} />
                      <FlameAsk {...ASK.titleName} />
                    </label>
                    <button type="button" className="sec-btn sec-btn-ghost flame-drop" onClick={() => setTitles((rows) => rows.filter((_, i) => i !== index))}>Убрать</button>
                  </li>
                ))}
                </ul>
                <div className="flame-actions">
                  <button
                    type="button"
                    className="sec-btn"
                    disabled={busy === 'titles'}
                    onClick={() => run('titles', () => saveFlameTitles({
                      titles: titles
                        .map((row) => ({ fromDay: Number(row.fromDay), title: row.title.trim(), emojiId: row.emojiId }))
                        .filter((row) => row.fromDay >= 1 && row.title),
                    }))}
                  >
                    {busy === 'titles' ? 'Сохраняем…' : 'Сохранить статусы'}
                  </button>
                </div>
              </FlameFold>
              <div className="flame-actions">
                <button type="button" className="sec-btn" disabled={busy === 'settings'} onClick={saveAllSettings}>Сохранить переключатель</button>
              </div>
            </section>
          )}

          {tab === 'gift' && (
            <section className="flame-card">
              <div className="flame-card-head">
                <h3>Бонус + · предмет 🎁</h3>
                <div className="flame-ask-slot">
                  <FlameSwitch checked={form.giftEnabled} onChange={(e) => patch('giftEnabled', e.target.checked)}>
                    {form.giftEnabled ? 'Работает' : 'Выключен'}
                  </FlameSwitch>
                  <FlameAsk {...ASK.gift} />
                </div>
              </div>
              <p className="flame-note">
                {form.giftEnabled
                  ? 'Человек пишет «использовать 🎁», нажимает «Открыть Бонус +» и выбирает одну клетку. Что внутри — только после выбора.'
                  : 'Пока выключен. «использовать 🎁» ничего не откроет.'}
              </p>
              <FlameFold open={Boolean(form.giftEnabled)}>
              <p className="flame-note">
                Интро без цифр. «Что можно получить?» берёт куты из полей и предметы с галочкой «В списке».
              </p>
              <CellBoard
                cells={form.giftCellEmojis}
                onChange={(giftCellEmojis) => patch('giftCellEmojis', giftCellEmojis)}
              />
              <div className="flame-grid-2">
                <label className="flame-field">
                  <span>Умножение клеток</span>
                  <input inputMode="numeric" value={form.giftMult} onChange={(e) => patch('giftMult', digits(e.target.value))} />
                  <FlameAsk {...ASK.giftMult} />
                </label>
                <label className="flame-field">
                  <span>Куты на клетке: от</span>
                  <input inputMode="numeric" value={form.giftKutyMin} onChange={(e) => patch('giftKutyMin', digits(e.target.value))} />
                  <FlameAsk {...ASK.giftKutyMin} />
                </label>
                <label className="flame-field">
                  <span>Куты на клетке: до</span>
                  <input inputMode="numeric" value={form.giftKutyMax} onChange={(e) => patch('giftKutyMax', digits(e.target.value))} />
                  <FlameAsk {...ASK.giftKutyMax} />
                </label>
                <label className="flame-field">
                  <span>Запасные куты, % от цены</span>
                  <input inputMode="numeric" value={form.giftFallbackPct} onChange={(e) => patch('giftFallbackPct', digits(e.target.value))} />
                  <FlameAsk {...ASK.giftFallback} />
                </label>
              </div>
              <p className="flame-note">
                Куты и покупки — только с техгрупп / магазина / биржи. Нет остатка → слот пустой.
              </p>

              <div className="flame-card-head">
                <h3>Доп. куты</h3>
                <div className="flame-ask-slot">
                  <FlameSwitch checked={form.giftExtraKutyOn} onChange={(e) => patch('giftExtraKutyOn', e.target.checked)}>
                    {form.giftExtraKutyOn ? 'Включены' : 'Выключены'}
                  </FlameSwitch>
                  <FlameAsk {...ASK.extra} />
                </div>
              </div>
              <FlameFold open={Boolean(form.giftExtraKutyOn)}>
                <div className="flame-grid-2">
                  <label className="flame-field">
                    <span>Шанс, %</span>
                    <input inputMode="numeric" value={form.giftExtraKutyChance} onChange={(e) => patch('giftExtraKutyChance', digits(e.target.value))} />
                    <FlameAsk {...ASK.extraChance} />
                  </label>
                  <label className="flame-field">
                    <span>От</span>
                    <input inputMode="numeric" value={form.giftExtraKutyMin} onChange={(e) => patch('giftExtraKutyMin', digits(e.target.value))} />
                    <FlameAsk {...ASK.extraMin} />
                  </label>
                  <label className="flame-field">
                    <span>До</span>
                    <input inputMode="numeric" value={form.giftExtraKutyMax} onChange={(e) => patch('giftExtraKutyMax', digits(e.target.value))} />
                    <FlameAsk {...ASK.extraMax} />
                  </label>
                </div>
              </FlameFold>

              <div className="flame-preview">
                <h4>Кнопка «Что можно получить?»</h4>
                <p className="flame-consequence">
                  <b>Куты</b><br />
                  {playerReveal.kuty.map((line) => (
                    <span key={line} className="flame-reveal-line">· {line}</span>
                  ))}
                </p>
              </div>

              <div className="flame-card-head">
                <h3>Предметы</h3>
                <div className="flame-ask-slot">
                  <FlameSwitch checked={form.giftItemOn} onChange={(e) => patch('giftItemOn', e.target.checked)}>
                    {form.giftItemOn ? 'Включены' : 'Выключены'}
                  </FlameSwitch>
                  <FlameAsk {...ASK.items} />
                </div>
              </div>
              <FlameFold open={Boolean(form.giftItemOn)}>
              <p className="flame-note">
                Отметьте несколько предметов. Именно они выпадают в Бонусе +. Повторное нажатие в каталоге снимает выбор.
              </p>
              <DexItemSearchPicker
                addMode
                catalog={catalog}
                value=""
                valueMode="name"
                compact
                clearable={false}
                takenNames={bonusItems.map((row) => row.itemName)}
                onChange={addBonusItem}
                onRemove={removeBonusItem}
                label="Какие предметы выпадают"
                emptyLabel={bonusItems.length ? `Выбрано ${bonusItems.length} · добавить ещё` : 'Выбрать несколько предметов'}
                placeholder="Название или эмодзи…"
                hint="Можно отметить несколько подряд. Уже выбранные подсвечены."
              />
              {bonusItems.length === 0 ? (
                <p className="flame-note">Пока пусто. Пока предметов нет, в открытии будут только куты.</p>
              ) : (
                <ul className="bonus-pool">
                  {bonusItems.map((row) => {
                    const face = catalogFace(catalog, row.itemName)
                    const name = String(row.itemName || '').trim()
                    return (
                      <li key={name} className={row.showPreview ? 'bonus-pick is-shown' : 'bonus-pick'}>
                        <span className="bonus-pick-emoji" aria-hidden="true">{face?.emoji || '📦'}</span>
                        <div className="bonus-pick-main">
                          <strong>{name}</strong>
                          <label className="bonus-pick-show">
                            <input
                              type="checkbox"
                              checked={Boolean(row.showPreview)}
                              onChange={(e) => patchBonusItem(name, { showPreview: e.target.checked })}
                            />
                            <span>{row.showPreview ? 'Виден до открытия' : 'Скрыт, но может выпасть'}</span>
                          </label>
                        </div>
                        <label className="bonus-pick-weight">
                          <span>Вес</span>
                          <input
                            inputMode="numeric"
                            aria-label={`Вес: ${name}`}
                            value={row.weight}
                            onChange={(e) => patchBonusItem(name, { weight: digits(e.target.value) })}
                          />
                        </label>
                        <button type="button" className="sec-btn sec-btn-ghost" onClick={() => removeBonusItem(name)}>Убрать</button>
                      </li>
                    )
                  })}
                </ul>
              )}
              <div className="flame-ask-row">
                <FlameAsk {...ASK.giftShow} />
                <FlameAsk {...ASK.giftWeight} />
                <FlameAsk {...ASK.giftItem} />
              </div>
              <div className="flame-grid-2">
                <label className="flame-field">
                  <span>Шанс на каждый слот, %</span>
                  <input inputMode="numeric" value={form.giftItemChance} onChange={(e) => patch('giftItemChance', digits(e.target.value))} />
                  <FlameAsk {...ASK.itemChance} />
                </label>
                <label className="flame-field">
                  <span>Сколько разных за раз (1–5)</span>
                  <input inputMode="numeric" value={form.giftItemCount} onChange={(e) => patch('giftItemCount', digits(e.target.value))} />
                  <FlameAsk {...ASK.itemCount} />
                </label>
              </div>
              <p className="flame-note">{bonusDropLine}</p>
              {bonusItems.length > 0 && !bonusGivesAll && (
                <div className="flame-actions">
                  <button
                    type="button"
                    className="sec-btn sec-btn-ghost"
                    onClick={() => {
                      patch('giftItemCount', String(Math.min(5, bonusItems.length)))
                      patch('giftItemChance', '100')
                    }}
                  >
                    Выдавать выбранные за раз
                  </button>
                </div>
              )}
              <div className="flame-preview">
                {playerReveal.shownNames.length > 0 ? (
                  <p className="flame-consequence">
                    <b>
                      {playerReveal.slots <= 1
                        ? 'Предмет · до 1 за раз'
                        : `Предметы · до ${playerReveal.slots} за раз`}
                      {playerReveal.hiddenNames.length > 0 ? ' · в списке не всё' : ''}
                    </b>
                    {playerReveal.shownNames.map((name) => (
                      <span key={name} className="flame-reveal-line">· {name}</span>
                    ))}
                  </p>
                ) : (
                  <p className="flame-note">В списке до открытия пусто — игрок увидит только куты, пока не выпадет скрытый предмет.</p>
                )}
                {playerReveal.hiddenNames.length > 0 && (
                  <p className="flame-note">
                    Скрыто от списка, но может выпасть: {playerReveal.hiddenNames.join(' · ')}
                  </p>
                )}
              </div>
              </FlameFold>
              </FlameFold>
              <div className="flame-actions">
                <button type="button" className="sec-btn" disabled={busy === 'settings'} onClick={saveBonusPlus}>
                  {busy === 'settings' ? 'Сохраняем…' : 'Сохранить Бонус +'}
                </button>
              </div>
            </section>
          )}

          {tab === 'restore' && (
            <section className="flame-card">
              <div className="flame-card-head">
                <h3>Вернуть погасший огонёк</h3>
                <div className="flame-ask-slot">
                  <FlameSwitch checked={form.restoreEnabled} onChange={(e) => patch('restoreEnabled', e.target.checked)}>
                    {form.restoreEnabled ? 'Возврат включён' : 'Возврат выключен'}
                  </FlameSwitch>
                  <FlameAsk {...ASK.restore} />
                </div>
              </div>
              <FlameFold open={Boolean(form.restoreEnabled)}>
              <p className="flame-note">
                Человек пишет «вернуть огонёк». Серия поднимается на столько дней, сколько сгорело. Сегодня до 00:00 по Москве огонёк всё равно нужно продлить снова, иначе он погаснет. Новая серия сжигает старую: после этого прошлую уже не вернуть.
              </p>
              <div className="flame-grid-2">
                <label className="flame-field">
                  <span>Сколько дней можно вернуть</span>
                  <input inputMode="numeric" value={form.restoreDays} onChange={(e) => patch('restoreDays', digits(e.target.value))} />
                  <FlameAsk {...ASK.restoreDays} />
                </label>
                <label className="flame-field">
                  <span>Цена в кутах, 0 — без кут</span>
                  <input inputMode="numeric" value={form.restoreKuty} onChange={(e) => patch('restoreKuty', digits(e.target.value))} />
                  <FlameAsk {...ASK.restoreKuty} />
                </label>
              </div>
              <FlameItemPick
                catalog={catalog}
                label="Предмет"
                value={form.restoreItem || ''}
                emptyLabel="Не брать предмет"
                ask={ASK.restoreItem}
                onChange={(restoreItem) => patch('restoreItem', restoreItem)}
              />
              <FlameFold open={Boolean(String(form.restoreItem || '').trim())}>
                <label className="flame-field">
                  <span>Сколько предметов списать</span>
                  <input
                    inputMode="numeric"
                    value={form.restoreItemCount}
                    onChange={(e) => patch('restoreItemCount', digits(e.target.value))}
                  />
                  <FlameAsk {...ASK.restoreCount} />
                </label>
              </FlameFold>
              <p className="flame-preview-line">{restoreHint}</p>
              </FlameFold>
              <div className="flame-actions">
                <button type="button" className="sec-btn" disabled={busy === 'settings'} onClick={saveAllSettings}>
                  {busy === 'settings' ? 'Сохраняем…' : 'Сохранить возврат'}
                </button>
              </div>
            </section>
          )}

          {tab === 'live' && (
            <>
              <section className="flame-card">
                <h3>Живые серии</h3>
                {(board.people || []).length === 0 && <p className="flame-empty">Пока никто не держит огонёк.</p>}
                <ol className="flame-people">
                  {(board.people || []).map((person) => (
                    <li key={person.userId}>
                      <strong>{person.name}{person.title ? ` · ${person.title}` : ''}</strong>
                      <span>{person.record ? `рекорд ${person.label}` : person.label}</span>
                    </li>
                  ))}
                </ol>
              </section>
              <section className="flame-card">
                <h3>Последние награды</h3>
                <p className="flame-note">Всё, что люди реально получили: дни серии, тёплый час и 🎁.</p>
                {(board.loot || []).length === 0 && <p className="flame-empty">Пока пусто — награды появятся сами.</p>}
                <ul className="flame-loot">
                  {(board.loot || []).map((row) => (
                    <li key={row.id}>
                      <div>
                        <strong>{row.name}</strong>
                        <span>{sourceLabel(row.source)}</span>
                      </div>
                      <em>{row.label}</em>
                    </li>
                  ))}
                </ul>
              </section>
            </>
          )}
          </div>
          </div>
        </>
      )}
    </section>
  )
}
