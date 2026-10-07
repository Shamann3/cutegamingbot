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
  { id: 'settings', label: 'Настройки' },
]

const LEVEL_CAP = 12

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
  ['glowPrice', 'Блик, кут', 'Маленькая искра только купившему. Лишнее остаётся и сгорает по норме дня'],
  ['glowCare', 'Забота от блика', 'Сколько заботы блик кладёт тому, кто его использовал'],
  ['candlePrice', 'Свеча, кут', 'Средняя искра только купившему. Лишнее остаётся и сгорает по норме дня'],
  ['candleCare', 'Забота от свечи', 'Сколько заботы свеча даёт тому, кто её зажёг'],
  ['hearthPrice', 'Очаг, кут', 'Большая искра только купившему. Лишнее остаётся и сгорает по норме дня'],
  ['hearthCare', 'Забота от очага', 'Сколько заботы очаг кладёт тому, кто его разжёг'],
  ['matchPrice', 'Спичка, кут', 'Закрывает только его половину вчера, и только пока искра гаснет'],
  ['ribbonPrice', 'Лента, кут', 'Один раз на пару. Знак в профиле, к искре ничего не прибавляет'],
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
        Это путь пары в чате. Половина заботы считается сама: если вместе 10, с каждого по 5.
        Карточка переезжает, как только меняется день.
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

export default function MarriageSection() {
  const [period, setPeriod] = useState('week')
  const [lens, setLens] = useState('picture')
  const [board, setBoard] = useState(null)
  const [form, setForm] = useState(null)
  const [verbs, setVerbs] = useState([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

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
              {LENSES.map((item) => (
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
                  <button type="button" className="mrg-path" onClick={() => setLens('levels')}>
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

          {lens === 'levels' && form && (
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

          {lens === 'settings' && form && (
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
              <h3 className="realm-h">Цена жеста</h3>
              <p className="act-read">0 — жест бесплатный. Больше нуля — бот сначала спрашивает и называет кнопку со суммой.</p>
              <div className="mrg-form">
                {verbs.map((item) => (
                  <label key={item.id}>
                    {item.title}
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
        </div>
      )}
    </section>
  )
}
