import { useEffect, useMemo, useRef, useState } from 'react'
import { fetchMarriageBoard, saveMarriageSettings } from '../../lib/adminClient'

const PERIODS = [
  { id: 'day', label: 'Сегодня' },
  { id: 'week', label: '7 дней' },
  { id: 'month', label: 'Месяц' },
  { id: 'year', label: 'Год' },
]

const LENSES = [
  { id: 'picture', label: 'Картина' },
  { id: 'pairs', label: 'Пары' },
  { id: 'levels', label: 'Уровни' },
  { id: 'items', label: 'Предметы' },
  { id: 'feast', label: 'Праздники' },
  { id: 'settings', label: 'Настройки' },
]

const SHELF = [
  ['glow', '🎇', 'Блик брака', 'glowPrice', 'glowCare', 'Вам +3. Лишнее остаётся на следующие дни.'],
  ['candle', '🕯', 'Свеча брака', 'candlePrice', 'candleCare', 'Вам +8. Лишнее остаётся на следующие дни.'],
  ['hearth', '🎆', 'Очаг брака', 'hearthPrice', 'hearthCare', 'Вам +20. Лишнее остаётся на следующие дни.'],
  ['match', '🪔', 'Спичка брака', 'matchPrice', '', 'Пока искра гаснет: дожигает вашу вчерашнюю половину.'],
  ['ribbon', '🎀', 'Лента брака', 'ribbonPrice', '', 'Ваш знак в профиле. Партнёр покупает свою.'],
]

const LEVEL_CAP = 12
const EFFECTS = [
  { id: 'self', label: 'Тепло себе', care: 'Забота' },
  { id: 'other', label: 'Тепло партнёру', care: 'Забота' },
  { id: 'both', label: 'Тепло обоим', care: 'Забота' },
  { id: 'norm', label: 'Ночью добить свою норму', care: '' },
  { id: 'dawn', label: 'Утром, пока искра гаснет', care: 'Забота' },
  { id: 'gap', label: 'Дожечь вчерашнюю половину', care: '' },
  { id: 'vow', label: 'Один раз дописать день после ответа', care: '' },
  { id: 'mark', label: 'Свой знак в профиле', care: '' },
  { id: 'propose', label: 'Сделать предложение', care: '' },
  { id: 'ring', label: 'Отдать кольцо после предложения', care: '' },
  { id: 'seed', label: 'Саженец на ферму', care: '' },
  { id: 'pantry', label: 'Овощ для крафта', care: '' },
]

const LIFE = [
  'Вы ещё узнаёте друг друга. Ответа на сегодня уже достаточно.',
  'Уже хочется написать первым.',
  'Разговор стал привычкой, как чай вечером.',
  'Молчание уже понятно. Ответ всё равно нужен обоим.',
  'У вас уже есть свой тон. День без него заметен.',
  'Забота находится сама. Кладут её всё равно оба.',
  'Вы держитесь обычными словами. Комната от этого тише.',
  'Обещание уже живёт в обычном ответе.',
  'Вечер узнаётся без объяснений.',
  'Тепло остаётся, даже если день был коротким.',
  'Вы узнаёте друг друга по одной фразе.',
  'Этот день такой же, как вчерашний. И от этого спокойно.',
]

const FIELDS = [
  ['freeWeddings', 'Бесплатных свадеб', 'Сколько первых свадеб человека ничего не стоят'],
  ['firstPaid', 'Первая платная, кут', 'Цена свадьбы сразу после бесплатных'],
  ['doubleUntil', 'Потолок удвоения', 'Дальше цена не прыгает вдвое, а растёт на процент'],
  ['afterPercent', 'Процент после потолка', 'Каждая следующая свадьба дороже на столько процентов'],
  ['proposalMinutes', 'Минуты на ответ', 'Потом заявка закрывается и ничего не списывает'],
  ['rpPerDay', 'Один жест в сутки, раз', 'Столько раз пара может повторить одно и то же слово'],
  ['topLimit', 'Пар в топе группы', 'Сколько строк показывает «топ браков»'],
  ['toneStart', 'Тонус в день свадьбы', 'От 0 до 100. 80 уже считается «в тонусе»'],
  ['toneGain', 'Жест прибавляет', 'Только первый жест новых суток'],
  ['toneDecay', 'День без жеста снимает', 'Старое поле тонуса. Игру искры оно больше не двигает'],
  ['rescueHours', 'Часы, чтобы спасти искру', 'После полуночи оба ещё успевают закрыть вчера. От 1 до 48'],
  ['moonFrom', 'Луна с часа', 'По Москве, 0–23. Вместе с «Луна до часа» это ночное окно'],
  ['moonTo', 'Луна до часа', 'По Москве, 0–23. 6 значит до 06:00, сам час уже не считается'],
  ['dawnFrom', 'Рассвет с часа', 'По Москве, 0–23'],
  ['dawnTo', 'Рассвет до часа', 'По Москве, 0–23. 10 значит до 10:00'],
  ['replyCare', 'Ответ партнёру, забота', 'Короткий ответ. 0 — ответ день отмечает, искру не двигает'],
  ['replyWarm', 'Длинный ответ, забота', 'Если слов не меньше порога ниже'],
  ['replyWarmWords', 'Слов для длинного ответа', 'Столько слов и больше — берётся длинная забота'],
  ['replyAlmost', 'Когда написать в чат', 'Сообщение один раз, когда до своей половины осталось столько'],
]

function fmt(value) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  return new Intl.NumberFormat('ru-RU').format(Number(value))
}

function delta(now, before, noun) {
  const current = Number(now)
  const past = Number(before)
  if (!Number.isFinite(current) || !Number.isFinite(past)) return `${noun}: прошлый срок не посчитался.`
  if (past <= 0 && current <= 0) return `${noun}: и сейчас, и в прошлый срок было 0.`
  if (past <= 0) return `${noun}: в прошлый срок было 0, сейчас ${fmt(current)}.`
  const pct = Math.round(((current - past) / past) * 100)
  if (pct === 0) return `${noun}: столько же, сколько в прошлый срок.`
  return `${noun}: на ${Math.abs(pct)}% ${pct > 0 ? 'больше' : 'меньше'}, чем в прошлый срок.`
}

function levelOf(value, max) {
  if (value <= 0 || max <= 0) return 0
  const t = value / max
  if (t < 0.25) return 1
  if (t < 0.5) return 2
  if (t < 0.75) return 3
  return 4
}

function nextPrice(price, cap, percent) {
  if (price < cap) {
    const doubled = price * 2
    return doubled <= cap ? doubled : cap
  }
  return Math.floor((price * (100 + percent) + 50) / 100)
}

function ladderOf(form) {
  const free = Math.max(0, Number(form.freeWeddings) || 0)
  const first = Math.max(0, Number(form.firstPaid) || 0)
  const cap = Math.max(1, Number(form.doubleUntil) || 1)
  const percent = Math.max(0, Number(form.afterPercent) || 0)
  const rows = []
  for (let done = 0; done < 12; done += 1) {
    let price = 0
    if (done >= free) {
      price = first
      for (let step = 0; step < done - free; step += 1) price = nextPrice(price, cap, percent)
    }
    rows.push({ wedding: done + 1, price })
  }
  return rows
}

function together(days) {
  const n = Number(days) || 0
  if (n <= 0) return 'сегодня'
  if (n === 1) return '1 день'
  if (n < 5) return `${n} дня`
  return `${n} дн.`
}

function shareOf(goal) {
  const whole = Math.max(2, Number(goal) || 0)
  if (!Number.isFinite(whole) || whole <= 0) return 1
  return Math.max(1, Math.floor((whole + 1) / 2))
}

function stampLevels(settings) {
  if (!settings) return settings
  const levels = Array.isArray(settings.levels) ? settings.levels : []
  return {
    ...settings,
    levels: levels.map((row, index) => ({
      ...row,
      key: row.key || `s${row.id ?? index}`,
    })),
  }
}

function levelsPayload(rows) {
  return (Array.isArray(rows) ? rows : []).map((row) => ({
    name: row?.name ?? '',
    days: Number(row?.days) || 0,
    goal: Number(row?.goal) || 0,
  }))
}

function tidyDays(rows) {
  const tagged = (rows || []).map((row, index) => ({ ...row, order: index }))
  tagged.sort((a, b) => (Number(a.days) || 0) - (Number(b.days) || 0) || a.order - b.order)
  if (tagged.length) tagged[0] = { ...tagged[0], days: 0 }
  const used = new Set()
  return tagged.map((row, index) => {
    let day = Math.max(0, Math.min(3650, Number(row.days) || 0))
    while (used.has(day) && day < 3650) day += 1
    used.add(day)
    const goal = Number(row.goal)
    return {
      key: row.key,
      name: row.name,
      days: day,
      goal: Number.isFinite(goal) ? goal : 10,
      id: index + 1,
    }
  })
}

function LevelEditor({ levels, onChange }) {
  const [armed, setArmed] = useState('')
  const [leaving, setLeaving] = useState('')
  const alive = useRef(true)
  useEffect(() => () => {
    alive.current = false
  }, [])
  const rows = Array.isArray(levels) ? levels : []
  const path = [...rows].sort((a, b) => (Number(a.days) || 0) - (Number(b.days) || 0))
  const startKey = path[0]?.key

  function update(key, field, value) {
    onChange((prev) => prev.map((row) => (row.key === key ? { ...row, [field]: value } : row)))
    setArmed('')
  }

  function addLevel() {
    onChange((prev) => {
      if (prev.length >= LEVEL_CAP) return prev
      const last = [...prev].sort((a, b) => (Number(a.days) || 0) - (Number(b.days) || 0)).at(-1) || { days: 0, goal: 10 }
      return tidyDays([
        ...prev,
        {
          key: `n${Date.now()}`,
          name: 'Новый',
          days: Math.min(3650, (Number(last.days) || 0) + 7),
          goal: Math.min(500, (Number(last.goal) || 10) + 6),
        },
      ])
    })
    setArmed('')
  }

  function move(key, direction) {
    onChange((prev) => {
      const ordered = tidyDays(prev)
      const index = ordered.findIndex((row) => row.key === key)
      const swap = index + direction
      if (index < 0 || swap < 0 || swap >= ordered.length) return prev
      const daysA = Number(ordered[index].days) || 0
      const daysB = Number(ordered[swap].days) || 0
      const next = ordered.map((row) => ({ ...row }))
      next[index] = { ...next[index], days: daysB }
      next[swap] = { ...next[swap], days: daysA }
      return tidyDays(next)
    })
    setArmed('')
  }

  function remove(key) {
    if (rows.length <= 1) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) {
      onChange((prev) => tidyDays(prev.filter((row) => row.key !== key)))
      setArmed('')
      return
    }
    setLeaving(key)
    window.setTimeout(() => {
      onChange((prev) => tidyDays(prev.filter((row) => row.key !== key)))
      if (!alive.current) return
      setLeaving('')
      setArmed('')
    }, 180)
  }

  return (
    <div className="mrg-levels-wrap">
      <p className="mrg-path" aria-label="Как уровни идут в чате">
        {path.map((row, index) => (
          <span key={row.key || index}>
            {index > 0 && <i aria-hidden="true">→</i>}
            {String(row.name || '…').trim() || '…'}
          </span>
        ))}
      </p>
      <p className="act-read">
        Это путь пары в чате. С каждой ступенью им живётся привычнее: сначала достаточно ответа, потом появляется свой тон, потом вечер узнаётся сам.
        Половина заботы считается сама. Если вместе 10, с каждого по 5.
      </p>
      <ol className="mrg-levels">
        {path.map((row, index) => {
          const goal = Number(row.goal) || 0
          const share = shareOf(goal)
          const start = row.key === startKey
          return (
            <li
              key={row.key || index}
              className={`mrg-level${leaving === row.key ? ' is-leaving' : ''}${start ? ' is-first' : ''}`}
              style={{ animationDelay: `${Math.min(index, 8) * 40}ms` }}
            >
              <div className="mrg-level-head">
                <b>{index + 1}</b>
                <span>по {share} с каждого · вместе {goal || '—'}</span>
              </div>
              {LIFE[index] ? <p className="mrg-level-life">{LIFE[index]}</p> : null}
              <div className="mrg-level-fields">
                <label>
                  Имя в чате
                  <input
                    className="sec-input"
                    maxLength={24}
                    value={row.name ?? ''}
                    onChange={(event) => update(row.key, 'name', event.target.value.slice(0, 24))}
                    onBlur={() => {
                      onChange((prev) => prev.map((item, itemIndex) => {
                        if (item.key !== row.key) return item
                        const name = String(item.name || '').replace(/[<>&]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 24)
                        return { ...item, name: name || `Уровень ${itemIndex + 1}` }
                      }))
                    }}
                  />
                </label>
                <label>
                  С какого дня серии
                  <input
                    className="sec-input"
                    type="number"
                    min="0"
                    max="3650"
                    disabled={start}
                    value={start ? 0 : (row.days ?? 0)}
                    onChange={(event) => update(row.key, 'days', event.target.value === '' ? 0 : Number(event.target.value))}
                    onBlur={() => onChange((prev) => tidyDays(prev))}
                  />
                  <em>{start ? 'Серия начинается здесь. Этот день всегда 0.' : 'День, с которого пара входит на этот уровень.'}</em>
                </label>
                <label>
                  Забота вместе
                  <input
                    className="sec-input"
                    type="number"
                    min="2"
                    max="500"
                    value={row.goal ?? 0}
                    onChange={(event) => update(row.key, 'goal', event.target.value === '' ? 0 : Number(event.target.value))}
                    onBlur={() => {
                      onChange((prev) => prev.map((item) => {
                        if (item.key !== row.key) return item
                        const number = Number(item.goal)
                        const next = Number.isFinite(number) ? Math.max(2, Math.min(500, Math.round(number))) : 10
                        return { ...item, goal: next }
                      }))
                    }}
                  />
                  <em>Оба должны закрыть свою половину. Один за двоих день не закрывает.</em>
                </label>
              </div>
              <div className="mrg-level-actions">
                <button type="button" disabled={index === 0} onClick={() => move(row.key, -1)}>Выше</button>
                <button type="button" disabled={index === path.length - 1} onClick={() => move(row.key, 1)}>Ниже</button>
                {armed === row.key ? (
                  <>
                    <button type="button" onClick={() => setArmed('')}>Оставить</button>
                    <button type="button" className="is-danger" onClick={() => remove(row.key)}>Точно убрать</button>
                  </>
                ) : (
                  <button
                    type="button"
                    className="is-danger"
                    disabled={rows.length <= 1}
                    title={rows.length <= 1 ? 'Последний уровень остаётся: серии нужно с чего-то начаться' : 'Убрать этот уровень'}
                    onClick={() => setArmed(row.key)}
                  >
                    Удалить
                  </button>
                )}
              </div>
            </li>
          )
        })}
      </ol>
      <div className="realm-actions">
        <button type="button" className="is-on" disabled={rows.length >= LEVEL_CAP} onClick={addLevel}>
          Добавить уровень
        </button>
      </div>
      {rows.length >= LEVEL_CAP && (
        <p className="act-read">Двенадцать уровней — потолок, чтобы экран в чате оставался коротким.</p>
      )}
    </div>
  )
}

export default function MarriageSection({ creator = false }) {
  const [period, setPeriod] = useState('week')
  const [lens, setLens] = useState('picture')
  const [board, setBoard] = useState(null)
  const [form, setForm] = useState(null)
  const [verbs, setVerbs] = useState([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [freshId, setFreshId] = useState('')

  useEffect(() => {
    let stop = false
    setLoading(true)
    setError('')
    fetchMarriageBoard(period)
      .then((data) => {
        if (stop) return
        setBoard(data)
        setForm((current) => current || stampLevels(data.settings))
        setVerbs((current) => (current.length ? current : data.verbs || []))
      })
      .catch((err) => {
        if (!stop) setError(err?.message || 'Цифры отношений не открылись')
      })
      .finally(() => {
        if (!stop) setLoading(false)
      })
    return () => {
      stop = true
    }
  }, [period])

  const ladder = useMemo(() => (form ? ladderOf(form) : []), [form])
  const points = board?.points || []
  const maxWeddings = Math.max(...points.map((point) => Number(point.weddings) || 0), 1)

  function patch(key, value) {
    setForm((current) => ({ ...(current || {}), [key]: value }))
    setNotice('')
  }

  function patchPrize(id, key, value) {
    setForm((current) => ({
      ...(current || {}),
      prizes: (current?.prizes || []).map((row) => (row.id === id ? { ...row, [key]: value } : row)),
    }))
    setNotice('')
  }

  function patchPeriod(day, name) {
    setForm((current) => ({
      ...(current || {}),
      periods: (current?.periods || []).map((row) => (Number(row.day) === Number(day) ? { ...row, name } : row)),
    }))
    setNotice('')
  }

  function patchShelf(id, key, value) {
    setForm((current) => ({
      ...(current || {}),
      shelf: (current?.shelf || []).map((row) => {
        if (row.id !== id) return row
        const next = { ...row, [key]: value }
        if (key === 'effect') {
          const known = Array.isArray(current?.effects) && current.effects.length ? current.effects : EFFECTS
          const found = known.find((item) => item.id === value)
          next.careLabel = found?.care || ''
        }
        return next
      }),
    }))
    setNotice('')
  }

  function dropShelfItem(id) {
    setForm((current) => ({
      ...(current || {}),
      shelf: (current?.shelf || []).filter((row) => row.id !== id || row.custom !== true),
    }))
    setNotice('')
  }

  function addShelfItem() {
    const id = `own${Date.now().toString(36)}`
    const row = {
      id,
      custom: true,
      name: 'Новая вещь',
      emoji: '🫧',
      line: 'Коротко: зачем она в браке.',
      price: 10,
      care: 1,
      careLabel: 'Забота',
      effect: 'self',
      on: true,
      buy: 'Купить',
      use: 'Использовать',
    }
    setForm((current) => ({ ...(current || {}), shelf: [...(current?.shelf || []), row] }))
    setFreshId(id)
    setNotice('')
  }

  async function save() {
    if (!form) return
    setSaving(true)
    setNotice('')
    setError('')
    try {
      const payload = {
        ...form,
        levels: levelsPayload(form.levels),
        verbs: Object.fromEntries(verbs.map((item) => [item.id, Number(item.price) || 0])),
        sparks: Object.fromEntries(verbs.map((item) => [item.id, Number(item.care) || 0])),
        waits: Object.fromEntries(verbs.map((item) => [item.id, Number(item.wait) || 0])),
      }
      const saved = await saveMarriageSettings(payload)
      const next = stampLevels(saved.settings)
      setForm(next)
      setBoard((current) => (current ? { ...current, settings: next } : current))
      setVerbs(saved.verbs || [])
      setNotice('Сохранено. Бот подхватит это примерно за 15 секунд. Уже открытая заявка держит цену, которая была в момент «брак».')
    } catch (err) {
      setError(err?.message || 'Не сохранилось')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className={`act-board${loading ? ' is-loading' : ''}`} aria-busy={loading}>
      {error && <p className="realm-alert" role="alert">{error}</p>}
      {loading && !board && <p className="realm-copy">Считаем браки…</p>}
      {board && (
        <div className="act-desk">
          <div className="act-toolbar">
            <div className="realm-actions" role="tablist" aria-label="За какой срок показать отношения">
              {PERIODS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={period === item.id ? 'is-on' : ''}
                  onClick={() => setPeriod(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <div className="act-lenses" role="tablist" aria-label="Что открыть">
              {LENSES.filter((item) => creator || item.id === 'picture' || item.id === 'pairs').map((item) => (
                <button
                  key={item.id}
                  type="button"
                  role="tab"
                  aria-selected={lens === item.id}
                  className={lens === item.id ? 'is-on' : ''}
                  onClick={() => setLens(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div className="act-kpis">
            <button type="button" className="act-kpi" onClick={() => setLens('pairs')}>
              <span>Сейчас в браке</span>
              <strong>{fmt(board.live)}</strong>
              <em className="act-delta">пар на весь проект</em>
            </button>
            <button type="button" className="act-kpi" onClick={() => setLens('picture')}>
              <span>Свадеб</span>
              <strong>{fmt(board.weddings)}</strong>
              <em className="act-delta">{delta(board.weddings, board.previousWeddings, 'Свадьбы')}</em>
            </button>
            <button type="button" className="act-kpi" onClick={() => setLens('picture')}>
              <span>Куты проекту</span>
              <strong>{fmt(board.kut)}</strong>
              <em className="act-delta">{delta(board.kut, board.previousKut, 'Куты')}</em>
            </button>
            <button type="button" className="act-kpi" onClick={() => setLens('pairs')}>
              <span>Средний тонус</span>
              <strong>{board.toneAvg == null ? '—' : fmt(board.toneAvg)}</strong>
              <em className="act-delta">из 100, только живые пары</em>
            </button>
          </div>

          {lens === 'picture' && (
            <div className="act-split">
              <div className="act-stage">
                <h3 className="realm-h">Свадьбы по дням</h3>
                <p className="act-read">
                  Заявок за срок: {fmt(board.proposals)}. {delta(board.proposals, board.previousProposals, 'Заявки')}
                  {' '}Разводов: {fmt(board.divorces)}. {delta(board.divorces, board.previousDivorces, 'Разводы')}
                </p>
                <div className="act-bars" aria-label="Свадьбы по дням">
                  {points.map((point) => {
                    const value = Number(point.weddings) || 0
                    const h = Math.max(6, Math.round((value / maxWeddings) * 100))
                    return (
                      <button
                        key={point.date}
                        type="button"
                        data-level={levelOf(value, maxWeddings)}
                        title={`${point.label}: ${fmt(value)} свадеб, ${fmt(point.kut)} кут`}
                        aria-label={`${point.label}: ${fmt(value)} свадеб`}
                      >
                        <i style={{ height: `${h}%` }} />
                      </button>
                    )
                  })}
                </div>
              </div>
              <div className="act-stage">
                <h3 className="realm-h">Как горит искра</h3>
                <p className="act-read">
                  Искры горят: {fmt(board.sparkLit || 0)}. Ещё можно спасти: {fmt(board.sparkFading || 0)}.
                  Лучшая серия: {fmt(board.sparkBest || 0)} дн.
                </p>
                {(board.settings?.levels || []).length > 0 && (
                  <button type="button" className="mrg-path" onClick={() => creator && setLens('levels')}>
                    {board.settings.levels.map((row, index) => (
                      <span key={row.id ?? index}>
                        {index > 0 && <i aria-hidden="true">→</i>}
                        {row.name}
                      </span>
                    ))}
                  </button>
                )}
                <ul className="act-people">
                  {(board.bands || []).map((band) => (
                    <li key={band.id}>
                      <span className="act-person-main">
                        <strong>{band.label}</strong>
                      </span>
                      <b className="act-people-count">{fmt(band.count)}</b>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {lens === 'pairs' && (
            <div className="act-split">
              <div className="act-stage">
                <h3 className="realm-h">Кто вместе дольше всех</h3>
                <p className="act-read">Сверху те, кто поженился раньше. Место здесь не покупается.</p>
                {(board.pairs || []).length === 0 && <p className="act-read">Живых браков пока нет.</p>}
                <ul className="act-people">
                  {(board.pairs || []).map((pair, index) => (
                    <li key={`${pair.a}-${pair.b}-${index}`}>
                      <span className="act-person-main">
                        <strong>{index + 1}. {pair.a} и {pair.b}</strong>
                        <span>вместе {together(pair.days)}{pair.tone ? ` · ${pair.tone}` : ''}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="act-stage">
                <h3 className="realm-h">Последние списания</h3>
                <p className="act-read">Свадьба и платный жест. Бесплатное сюда не попадает.</p>
                {(board.recent || []).length === 0 && <p className="act-read">За этот срок списаний не было.</p>}
                <ul className="act-people">
                  {(board.recent || []).map((row, index) => (
                    <li key={`${row.at}-${index}`}>
                      <span className="act-person-main">
                        <strong>{row.title}</strong>
                        <span>{row.name}</span>
                      </span>
                      <b className="act-people-count">{fmt(row.amount)}</b>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {creator && lens === 'levels' && form && (
            <div className="act-stage">
              <h3 className="realm-h">Уровни искры</h3>
              <p className="act-read">
                Имя, день серии и общая забота. Бот читает эту лестницу в карточке пары, на кнопке «Уровень» и в помощи.
                Последний уровень убрать нельзя: серии нужно с чего-то начаться.
              </p>
              <LevelEditor levels={form.levels || []} onChange={(updater) => {
                setForm((current) => {
                  const prev = Array.isArray(current?.levels) ? current.levels : []
                  const next = typeof updater === 'function' ? updater(prev) : updater
                  return { ...(current || {}), levels: next }
                })
                setNotice('')
              }}
              />
              {notice && <p className="act-read">{notice}</p>}
              <div className="realm-actions">
                <button type="button" className="is-on" disabled={saving} onClick={save}>
                  {saving ? 'Сохраняем…' : 'Сохранить уровни'}
                </button>
              </div>
            </div>
          )}

          {creator && lens === 'settings' && form && (
            <div className="act-stage">
              <h3 className="realm-h">Что можно менять</h3>
              <p className="act-read">
                Это правила всего проекта. В одной группе создатель по-прежнему пишет +браки и -браки.
                Выключить здесь — значит остановить новые заявки везде. Уже существующие пары смогут открыть карточку и развестись.
              </p>
              <div className="mrg-switches">
                <label className="mrg-switch">
                  <input type="checkbox" checked={Boolean(form.enabled)} onChange={(event) => patch('enabled', event.target.checked)} />
                  Новые браки и жесты включены
                </label>
                <label className="mrg-switch">
                  <input type="checkbox" checked={form.sparkOn !== false} onChange={(event) => patch('sparkOn', event.target.checked)} />
                  Игра искры: оба каждый день дают заботу
                </label>
                <label className="mrg-switch">
                  <input type="checkbox" checked={Boolean(form.toneOn)} onChange={(event) => patch('toneOn', event.target.checked)} />
                  Считать старый тонус
                </label>
                <label className="mrg-switch">
                  <input type="checkbox" checked={Boolean(form.showEmptyProfile)} onChange={(event) => patch('showEmptyProfile', event.target.checked)} />
                  В профиле писать «брака нет», если пары нет
                </label>
              </div>
              <div className="mrg-form">
                {FIELDS.map(([key, title, hint]) => (
                  <label key={key}>
                    {title}
                    <input
                      className="sec-input"
                      type="number"
                      min="0"
                      value={form[key] ?? 0}
                      onChange={(event) => patch(key, event.target.value === '' ? 0 : Number(event.target.value))}
                    />
                    <em>{hint}</em>
                  </label>
                ))}
                <label>
                  Строка, когда до половины осталось мало
                  <input
                    className="sec-input"
                    type="text"
                    maxLength={80}
                    value={form.replyAlmostText ?? ''}
                    onChange={(event) => patch('replyAlmostText', event.target.value)}
                  />
                  <em>{'{name} — партнёр, {left} — сколько ещё не хватает. Пустое вернёт фразу по умолчанию.'}</em>
                </label>
                <label>
                  Строка, когда половина только что закрылась
                  <input
                    className="sec-input"
                    type="text"
                    maxLength={80}
                    value={form.replyDone ?? ''}
                    onChange={(event) => patch('replyDone', event.target.value)}
                  />
                  <em>Пусто — в чат ничего. День уже закрыт — бот молчит в любом случае.</em>
                </label>
                <label>
                  Группа фонда подарков
                  <input
                    className="sec-input"
                    type="text"
                    inputMode="numeric"
                    value={form.giftFundChat ?? ''}
                    onChange={(event) => patch('giftFundChat', event.target.value.replace(/[^\d-]/g, ''))}
                  />
                  <em>Сюда ляжет доля с важной покупки пары. Отсюда же потом оплачиваются подарки.</em>
                </label>
                <label>
                  Кому отдать премиум проекта
                  <input
                    className="sec-input"
                    type="text"
                    maxLength={32}
                    value={form.premiumKeeper ?? ''}
                    onChange={(event) => patch('premiumKeeper', event.target.value.replace(/^@/, ''))}
                  />
                  <em>Предмет приходит этому человеку. Он сам передаёт подписку паре. Бот Telegram Premium не используется.</em>
                </label>
              </div>
              <h3 className="realm-h">Как пойдёт цена</h3>
              <p className="act-read">Номер свадьбы того, кто пишет «брак». Развод номер не обнуляет.</p>
              <ul className="mrg-ladder">
                {ladder.map((row) => (
                  <li key={row.wedding}>
                    <span>{row.wedding}</span>
                    <b>{row.price === 0 ? 'бесплатно' : `${fmt(row.price)} кут`}</b>
                  </li>
                ))}
              </ul>
              <h3 className="realm-h">Добрые слова и огонёк</h3>
              <p className="act-read">
                Это добрые действия из команд чата. Человек пишет их ответом своей паре.
                Искры — сколько заботы падает в сегодняшний день. Пауза — сколько минут ждать, прежде чем то же слово снова засчитается. 0 — без паузы.
                Цена — если больше нуля, бот сначала спрашивает про куты.
              </p>
              <div className="mrg-verbs">
                {verbs.map((item) => (
                  <article key={item.id}>
                    <header>
                      <b>{item.title}</b>
                      <span>{item.word}</span>
                    </header>
                    <label>
                      Искры
                      <input
                        className="sec-input"
                        type="number"
                        min="0"
                        value={item.care ?? 0}
                        onChange={(event) => {
                          const care = event.target.value === '' ? 0 : Number(event.target.value)
                          setVerbs((current) => current.map((row) => (row.id === item.id ? { ...row, care } : row)))
                        }}
                      />
                    </label>
                    <label>
                      Пауза, мин
                      <input
                        className="sec-input"
                        type="number"
                        min="0"
                        value={item.wait ?? 0}
                        onChange={(event) => {
                          const wait = event.target.value === '' ? 0 : Number(event.target.value)
                          setVerbs((current) => current.map((row) => (row.id === item.id ? { ...row, wait } : row)))
                        }}
                      />
                    </label>
                    <label>
                      Цена, кут
                      <input
                        className="sec-input"
                        type="number"
                        min="0"
                        value={item.price ?? 0}
                        onChange={(event) => {
                          const price = event.target.value === '' ? 0 : Number(event.target.value)
                          setVerbs((current) => current.map((row) => (row.id === item.id ? { ...row, price } : row)))
                        }}
                      />
                    </label>
                  </article>
                ))}
              </div>
              {notice && <p className="act-read">{notice}</p>}
              <div className="realm-actions">
                <button type="button" className="is-on" disabled={saving} onClick={save}>
                  {saving ? 'Сохраняем…' : 'Сохранить настройки'}
                </button>
              </div>
            </div>
          )}

          {creator && lens === 'items' && form && (
            <div className="act-stage">
              <h3 className="realm-h">Полка сердец</h3>
              <p className="act-read">
                Под названием игрок видит одну короткую фразу: что вещь даёт.
                Саженцы продаются. Овощи и ужин растут и собираются, их можно выключить с полки.
                У саженца здесь же минуты роста и число поливов.
              </p>
              <div className="realm-actions">
                <button type="button" onClick={addShelfItem}>Новая вещь</button>
              </div>
              <div className="mrg-shelf">
                {(Array.isArray(form.shelf) && form.shelf.length > 0 ? form.shelf : []).map((item) => {
                  const options = Array.isArray(form.effects) && form.effects.length ? form.effects : EFFECTS
                  const same = (form.shelf || []).filter((row) => row.on !== false && row.emoji && row.emoji === item.emoji).length
                  const quietClash = form.quietOn !== false && (form.quietEmoji || '🤫') === item.emoji
                  const clash = item.on !== false && (same > 1 || quietClash)
                  return (
                    <article key={item.id} className={`mrg-item${item.on === false ? ' is-off' : ''}${freshId === item.id ? ' is-fresh' : ''}`}>
                      <div className="mrg-item-head">
                        <label className="mrg-item-mark">
                          <input
                            className="mrg-mark-input"
                            aria-label={`Знак: ${item.name || 'вещь'}`}
                            maxLength={8}
                            value={item.emoji || ''}
                            onChange={(event) => patchShelf(item.id, 'emoji', event.target.value)}
                          />
                        </label>
                        <div className="mrg-item-copy">
                          <input
                            className="sec-input"
                            aria-label={`Название: ${item.name || 'вещь'}`}
                            maxLength={40}
                            value={item.name || ''}
                            onChange={(event) => patchShelf(item.id, 'name', event.target.value)}
                          />
                          <input
                            className="sec-input"
                            aria-label="Зачем в браке"
                            maxLength={140}
                            placeholder="Зачем эта вещь в браке"
                            value={item.line || ''}
                            onChange={(event) => patchShelf(item.id, 'line', event.target.value)}
                          />
                        </div>
                      </div>
                      <div className="mrg-item-fields">
                        <label className="mrg-span">
                          Что делает
                          <select
                            className="sec-input"
                            value={item.effect || 'self'}
                            onChange={(event) => patchShelf(item.id, 'effect', event.target.value)}
                          >
                            {options.map((option) => (
                              <option key={option.id} value={option.id}>{option.label}</option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Кут
                          <input
                            className="sec-input"
                            type="number"
                            min="0"
                            value={item.price ?? 0}
                            onChange={(event) => patchShelf(item.id, 'price', event.target.value === '' ? 0 : Number(event.target.value))}
                          />
                        </label>
                        {item.careLabel ? (
                          <label>
                            {item.careLabel}
                            <input
                              className="sec-input"
                              type="number"
                              min={item.careLabel === 'Часы' ? 1 : 0}
                              value={item.care ?? 0}
                              onChange={(event) => patchShelf(item.id, 'care', event.target.value === '' ? 0 : Number(event.target.value))}
                            />
                          </label>
                        ) : null}
                        {item.effect === 'seed' ? (
                          <>
                            <label>
                              Минуты
                              <input
                                className="sec-input"
                                type="number"
                                min="1"
                                max="1440"
                                value={item.growMin ?? 30}
                                onChange={(event) => patchShelf(item.id, 'growMin', event.target.value === '' ? 30 : Number(event.target.value))}
                              />
                            </label>
                            <label>
                              Поливы
                              <input
                                className="sec-input"
                                type="number"
                                min="0"
                                max="12"
                                value={item.waters ?? 3}
                                onChange={(event) => patchShelf(item.id, 'waters', event.target.value === '' ? 0 : Number(event.target.value))}
                              />
                            </label>
                          </>
                        ) : null}
                      </div>
                      <label className="mrg-switch">
                        <input
                          type="checkbox"
                          checked={item.on !== false}
                          onChange={(event) => patchShelf(item.id, 'on', event.target.checked)}
                        />
                        На полке
                      </label>
                      {item.custom ? (
                        <button type="button" onClick={() => dropShelfItem(item.id)}>Убрать вещь</button>
                      ) : null}
                      {clash ? <p className="mrg-clash">Этот знак уже занят. В магазине вещи перепутаются.</p> : null}
                    </article>
                  )
                })}
                {!(Array.isArray(form.shelf) && form.shelf.length > 0) && SHELF.map(([id, emoji, name, priceKey, careKey, line]) => (
                  <article key={id} className="mrg-item">
                    <div className="mrg-item-head">
                      <span className="mrg-item-mark" aria-hidden="true">{emoji}</span>
                      <div>
                        <strong>{name}</strong>
                        <p>{line}</p>
                      </div>
                    </div>
                    <div className="mrg-item-fields">
                      <label>
                        Кут
                        <input
                          className="sec-input"
                          type="number"
                          min="0"
                          value={form[priceKey] ?? 0}
                          onChange={(event) => patch(priceKey, event.target.value === '' ? 0 : Number(event.target.value))}
                        />
                      </label>
                      {careKey ? (
                        <label>
                          Забота
                          <input
                            className="sec-input"
                            type="number"
                            min="0"
                            value={form[careKey] ?? 0}
                            onChange={(event) => patch(careKey, event.target.value === '' ? 0 : Number(event.target.value))}
                          />
                        </label>
                      ) : null}
                    </div>
                  </article>
                ))}
                <article className="mrg-item">
                  <div className="mrg-item-head">
                    <span className="mrg-item-mark" aria-hidden="true">{form.quietEmoji || '🤫'}</span>
                    <div>
                      <strong>Тихий день</strong>
                      <p>Раз в неделю закрывает свою половину, если человек не успел ответить. Доля цены копится в фонд подарков.</p>
                    </div>
                  </div>
                  <label className="mrg-switch">
                    <input type="checkbox" checked={form.quietOn !== false} onChange={(event) => patch('quietOn', event.target.checked)} />
                    Продаётся на полке
                  </label>
                  <div className="mrg-item-fields">
                    <label>
                      Кут
                      <input className="sec-input" type="number" min="0" value={form.quietPrice ?? 40} onChange={(event) => patch('quietPrice', event.target.value === '' ? 0 : Number(event.target.value))} />
                    </label>
                    <label>
                      Знак
                      <input className="sec-input" type="text" maxLength={4} value={form.quietEmoji ?? ''} onChange={(event) => patch('quietEmoji', event.target.value)} />
                    </label>
                  </div>
                </article>
              </div>
              {notice && <p className="act-read">{notice}</p>}
              <div className="realm-actions">
                <button type="button" className="is-on" disabled={saving} onClick={save}>
                  {saving ? 'Сохраняем…' : 'Сохранить полку'}
                </button>
              </div>
            </div>
          )}

          {creator && lens === 'feast' && form && (
            <div className="act-stage">
              <h3 className="realm-h">Праздники пар</h3>
              <p className="act-read">
                Ответ партнёру ничего не стоит. Доля берётся только с «Тихого дня»: маленькая часть доли остаётся проекту, остальное копится в группе фонда и оттуда оплачивает подарок.
                Премиум приходит предметом @{form.premiumKeeper || 'JerichoCute'}. Он передаёт его сам. Бот Telegram Premium не вызывается.
              </p>
              <div className="mrg-form">
                <label>
                  Доля в фонд, %
                  <input className="sec-input" type="number" min="0" max="80" value={form.fundPercent ?? 20} onChange={(event) => patch('fundPercent', event.target.value === '' ? 0 : Number(event.target.value))} />
                  <em>Столько процентов цены уходит из покупки в комиссию.</em>
                </label>
                <label>
                  Проекту из этой доли, %
                  <input className="sec-input" type="number" min="0" max="80" value={form.projectKeepPercent ?? 10} onChange={(event) => patch('projectKeepPercent', event.target.value === '' ? 0 : Number(event.target.value))} />
                  <em>Остаток доли лежит в группе фонда.</em>
                </label>
                <label>
                  Конверт, кут
                  <input className="sec-input" type="number" min="0" value={form.envelopeKut ?? 15} onChange={(event) => patch('envelopeKut', event.target.value === '' ? 0 : Number(event.target.value))} />
                  <em>Если пара выбрала куты.</em>
                </label>
                <label>
                  Дополнительные куты
                  <input className="sec-input" type="number" min="0" value={form.extraKut ?? 0} onChange={(event) => patch('extraKut', event.target.value === '' ? 0 : Number(event.target.value))} />
                  <em>Прибавляются к конверту и к извинению, если предмет не купился.</em>
                </label>
              </div>
              <h3 className="realm-h">Как называются сроки</h3>
              <div className="mrg-form">
                {(form.periods || []).map((row) => (
                  <label key={row.day}>
                    {row.day} дней
                    <input className="sec-input" type="text" maxLength={24} value={row.name || ''} onChange={(event) => patchPeriod(row.day, event.target.value)} />
                  </label>
                ))}
              </div>
              <h3 className="realm-h">Что можно выбрать</h3>
              <div className="mrg-form">
                {(form.prizes || []).map((row) => (
                  <label key={row.id}>
                    <span className="mrg-switch">
                      <input type="checkbox" checked={Boolean(row.on)} onChange={(event) => patchPrize(row.id, 'on', event.target.checked)} />
                      {row.emoji} {row.name}
                    </span>
                    <input className="sec-input" type="text" maxLength={80} value={row.blurb || ''} onChange={(event) => patchPrize(row.id, 'blurb', event.target.value)} />
                    <em>Эта строка видна паре в том же сообщении.</em>
                  </label>
                ))}
              </div>
              {notice && <p className="act-read">{notice}</p>}
              <div className="realm-actions">
                <button type="button" className="is-on" disabled={saving} onClick={save}>
                  {saving ? 'Сохраняем…' : 'Сохранить праздники'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
