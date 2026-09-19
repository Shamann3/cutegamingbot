import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchGamesOverview, resetGameSettings, saveGamesSettings } from '../../lib/adminClient'
import { showToast } from '../../components/ToastHost'
import CountUp from '../../components/CountUp'
import Copyable, { CopyableId } from '../../components/Copyable'
import NikaMoneyChart from '../../components/NikaMoneyChart'
import { useIsPhone } from '../../lib/useIsDesktop'

const TABS = [
  { id: 'catalog', label: 'Стол', short: 'Стол' },
  { id: 'game', label: 'Игра', short: 'Игра' },
  { id: 'flow', label: 'Аналитика', short: 'Плюсы' },
  { id: 'commission', label: 'Комиссия', short: 'Комиссия' },
  { id: 'journal', label: 'Журнал', short: 'Журнал' },
  { id: 'machine', label: 'Как работает', short: 'Как' },
]

const GROUP_ORDER = ['odds', 'payout', 'table', 'tempo']
const GROUP_FALLBACK = {
  odds: 'Шансы',
  payout: 'Выплата',
  table: 'Стол',
  tempo: 'Темп',
}

function fmt(n) {
  return new Intl.NumberFormat('ru-RU').format(Number(n) || 0)
}

function pct(n) {
  return `${Math.round((Number(n) || 0) * 1000) / 10}%`
}

function signed(n) {
  const v = Number(n) || 0
  if (v > 0) return `+${fmt(v)}`
  if (v < 0) return `−${fmt(Math.abs(v))}`
  return '0'
}

function when(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

function clone(v) {
  return JSON.parse(JSON.stringify(v || {}))
}

function statusOf(state) {
  if (state?.maintenance) return { label: 'техработы', tone: 'hot' }
  if (state?.enabled) return { label: 'вкл', tone: 'ok' }
  return { label: 'выкл', tone: 'mute' }
}

function previewCommission(settings, gameKey, pot, level) {
  const comm = settings?.commission || {}
  if (!comm.enabled) return { amount: 0, rate: 0, note: 'комиссия выключена' }
  if (Number(pot) < Number(comm.minPot || 0)) return { amount: 0, rate: 0, note: 'банк меньше минимума' }
  const game = settings?.games?.[gameKey] || {}
  const base = Number(comm.rateByLevel?.[String(level)] || 0)
  const rate = Math.max(0, Math.min(1, base * Number(game.commissionMult || 0)))
  return { amount: Math.floor(Number(pot) * rate), rate, note: '' }
}

function previewPayout(game, state, pot) {
  const p = state?.params || {}
  const bet = Number(pot) || 0
  switch (game?.key) {
    case 'kube':
      return { label: 'Если угадал число', value: Math.floor(bet * Number(p.multiplier || 0)) }
    case 'slots':
      return { label: 'Три семёрки', value: Math.floor(bet * Number(p.tripleSeven || 0)) }
    case 'provoda':
      return { label: 'Верный провод', value: Math.floor(bet * Number(p.payout || 0)) }
    case 'trade':
      return { label: 'Верное направление, сверху', value: Math.floor(bet * Number(p.winMultiplier || 0)) }
    case 'balls':
      return { label: 'Угадал шарик, сверху', value: Math.floor(bet * Number(p.winMultiplier || 0)) }
    case 'fortuna_solo':
      return { label: 'Число', value: Math.floor(bet * Number(p.numberMult || 0)) }
    case 'tank':
    case 'plate':
    case 'risk':
      return { label: 'Один удачный шаг, сверху', value: Math.floor(bet * Number(p.stepMultiplier || 0)) }
    default:
      return null
  }
}

function Field({ label, help, children }) {
  return (
    <div className="gm-field">
      <span>{label}</span>
      {help ? <small>{help}</small> : null}
      <div className="gm-field-ctrl">{children}</div>
    </div>
  )
}

function Switch({ on, onClick, label }) {
  return (
    <button type="button" className="nika-ios-row" onClick={onClick}>
      <span>{label}</span>
      <i className={`nika-switch${on ? ' is-on' : ''}`} aria-hidden="true" />
    </button>
  )
}

function SliderNumber({ min, max, step, value, onChange }) {
  return (
    <>
      <input
        className="gm-range"
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <input
        className="gm-num"
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => {
          const next = Number(e.target.value)
          if (Number.isNaN(next)) return
          onChange(Math.max(min, Math.min(max, next)))
        }}
      />
    </>
  )
}

function ParamField({ field, value, onChange }) {
  const isChance = field.kind === 'chance'
  const isInt = field.kind === 'int'
  const lo = isChance ? Math.round(Number(field.min) * 1000) / 10 : Number(field.min)
  const hi = isChance ? Math.round(Number(field.max) * 1000) / 10 : Number(field.max)
  const shown = isChance ? Math.round(Number(value || 0) * 1000) / 10 : Number(value || 0)
  const step = isChance ? 0.1 : (isInt ? 1 : Number(field.step || 0.05))
  const label = isChance ? `${field.label}: ${shown}%` : `${field.label}: ${shown}`
  return (
    <Field label={label} help={field.hint}>
      <SliderNumber
        min={lo}
        max={hi}
        step={step}
        value={shown}
        onChange={(next) => onChange(isChance ? next / 100 : next)}
      />
    </Field>
  )
}

function cardChips(game, state) {
  const p = state?.params || {}
  const chips = [`${state?.minBet ?? 0}–${fmt(state?.maxBet || 0)}`]
  if (state?.maintenance) chips.push('техработы')
  else if (Number(state?.commissionMult) === 0) chips.push('без комиссии')
  else chips.push(`комиссия ×${Number(state?.commissionMult || 0).toFixed(2)}`)
  const first = (game.fields || [])[0]
  if (first) {
    const raw = p[first.key]
    if (first.kind === 'chance') chips.push(`${first.label} ${Math.round(Number(raw || 0) * 100)}%`)
    else if (first.kind === 'int') chips.push(`${first.label} ${raw}`)
    else chips.push(`${first.label} ${Number(raw || 0).toFixed(2)}`)
  }
  return chips
}

function FlowStrip({ plus, minus, plusHint, minusHint }) {
  const net = (Number(plus) || 0) - (Number(minus) || 0)
  return (
    <div className="nika-flow-hero is-compact">
      <div className="is-plus">
        <small>Оборот</small>
        <b className="nika-plus"><CountUp value={Number(plus) || 0} duration={900} /></b>
        {plusHint ? <em>{plusHint}</em> : null}
      </div>
      <div className="is-minus">
        <small>Комиссия</small>
        <b className="nika-minus"><CountUp value={Number(minus) || 0} duration={900} /></b>
        {minusHint ? <em>{minusHint}</em> : null}
      </div>
      <div>
        <small>Игрокам</small>
        <b className={net >= 0 ? 'nika-plus' : 'nika-minus'}>
          <CountUp value={net} signed duration={900} />
        </b>
      </div>
    </div>
  )
}

function GameAnalytics({ game, range, onRange, dayFilter, onFilter, phone }) {
  const points = range === 'hours' ? (game?.hours || []) : (game?.days || [])
  const extrema = range === 'hours' ? game?.hourExtrema : game?.dayExtrema
  const rows = useMemo(() => {
    const list = points.slice().reverse()
    if (dayFilter === 'plus') return list.filter((d) => (d.net || 0) > 0)
    if (dayFilter === 'minus') return list.filter((d) => (d.net || 0) < 0)
    return list
  }, [points, dayFilter])
  const plus = points.reduce((s, p) => s + (Number(p.plus) || 0), 0)
  const minus = points.reduce((s, p) => s + (Number(p.minus) || 0), 0)
  return (
    <section className="nika-panel nika-panel-chart">
      <div className="nika-panel-top">
        <div>
          <h2>Плюсы и минусы</h2>
          <p className="nika-help">
            Оборот — банки партий. Минус — комиссия в Фонд Роста. Итог — сколько ушло игрокам.
          </p>
        </div>
        <div className="nika-seg nika-seg-mini" role="group" aria-label="Масштаб">
          <button type="button" className={`nika-seg-btn${range === 'days' ? ' is-on' : ''}`} onClick={() => { onRange('days'); onFilter('all') }}>Дни</button>
          <button type="button" className={`nika-seg-btn${range === 'hours' ? ' is-on' : ''}`} onClick={() => { onRange('hours'); onFilter('all') }}>Часы</button>
        </div>
      </div>
      <FlowStrip plus={plus} minus={minus} plusHint={`${fmt(game?.stats?.events || 0)} партий`} minusHint="фонд роста" />
      {(extrema?.best || extrema?.worst) && (
        <div className="nika-extrema">
          {extrema.best ? (
            <article className="nika-ext is-plus">
              <small>Самый плюс</small>
              <strong>{extrema.best.label}</strong>
              <b className="nika-plus">{signed(extrema.best.net)}</b>
            </article>
          ) : null}
          {extrema.worst ? (
            <article className="nika-ext is-minus">
              <small>Самый минус</small>
              <strong>{extrema.worst.label}</strong>
              <b className="nika-minus">{signed(extrema.worst.net)}</b>
            </article>
          ) : null}
        </div>
      )}
      <NikaMoneyChart key={`${game?.key || 'game'}-${range}`} points={points} mode="flow" />
      <div className="nika-seg nika-seg-mini nika-filter" role="group" aria-label="Фильтр знака">
        <button type="button" className={`nika-seg-btn${dayFilter === 'all' ? ' is-on' : ''}`} onClick={() => onFilter('all')}>Все</button>
        <button type="button" className={`nika-seg-btn${dayFilter === 'plus' ? ' is-on' : ''}`} onClick={() => onFilter('plus')}>Только плюсы</button>
        <button type="button" className={`nika-seg-btn${dayFilter === 'minus' ? ' is-on' : ''}`} onClick={() => onFilter('minus')}>Только минусы</button>
      </div>
      <ul className="nika-days">
        {rows.slice(0, phone ? 10 : 18).map((d) => (
          <li key={d.t} className={(d.net || 0) > 0 ? 'is-plus' : (d.net || 0) < 0 ? 'is-minus' : 'is-flat'}>
            <i className="nika-days-pip" aria-hidden="true" />
            <span className="nika-days-when">{d.label}</span>
            <span className="nika-plus">+{fmt(d.plus)}</span>
            <span className="nika-minus">−{fmt(d.minus)}</span>
            <strong className={(d.net || 0) >= 0 ? 'nika-plus' : 'nika-minus'}>{signed(d.net)}</strong>
            <em className="nika-mute">{fmt(d.events || 0)} парт.</em>
          </li>
        ))}
      </ul>
      {rows.length === 0 && (
        <p className="nika-help">
          {dayFilter === 'minus' ? 'Минусов на этом отрезке ещё не было.' : dayFilter === 'plus' ? 'Плюсов на этом отрезке ещё не было.' : 'Партий ещё нет. Как сыграют — строка появится здесь.'}
        </p>
      )}
    </section>
  )
}

export default function GamesSection() {
  const phone = useIsPhone()
  const [tab, setTab] = useState('catalog')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [data, setData] = useState(null)
  const [draft, setDraft] = useState(null)
  const [query, setQuery] = useState('')
  const [kind, setKind] = useState('all')
  const [selected, setSelected] = useState(null)
  const [pot, setPot] = useState(100)
  const [level, setLevel] = useState(3)
  const [range, setRange] = useState('days')
  const [dayFilter, setDayFilter] = useState('all')
  const [flowScope, setFlowScope] = useState('game')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const next = await fetchGamesOverview()
      setData(next)
      setDraft(clone(next.settings))
    } catch (err) {
      showToast(err.message || 'Не открылся стол игр', 'error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const dirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(data?.settings), [draft, data])
  const games = data?.catalog || []
  const settings = draft || data?.settings || {}
  const shown = games.filter((g) => {
    if (kind !== 'all' && g.kind !== kind) return false
    const q = query.trim().toLowerCase()
    if (!q) return true
    return `${g.title} ${g.command} ${g.key} ${g.mood || ''}`.toLowerCase().includes(q)
  })
  const current = games.find((g) => g.key === selected) || shown[0] || games[0]
  const currentState = settings.games?.[current?.key] || current?.state || {}
  const groups = current?.groups || GROUP_FALLBACK
  const groupedFields = useMemo(() => {
    const fields = current?.fields || []
    const buckets = {}
    fields.forEach((field) => {
      const key = field.group || 'payout'
      if (!buckets[key]) buckets[key] = []
      buckets[key].push(field)
    })
    return GROUP_ORDER.filter((key) => buckets[key]).map((key) => ({
      key,
      label: groups[key] || GROUP_FALLBACK[key] || key,
      fields: buckets[key],
    }))
  }, [current, groups])

  const patchCommission = (key, value) => {
    setDraft((prev) => ({
      ...(prev || {}),
      commission: { ...((prev || {}).commission || {}), [key]: value },
    }))
  }

  const patchRate = (lvl, value) => {
    setDraft((prev) => ({
      ...(prev || {}),
      commission: {
        ...((prev || {}).commission || {}),
        rateByLevel: { ...(((prev || {}).commission || {}).rateByLevel || {}), [String(lvl)]: value },
      },
    }))
  }

  const patchGame = (key, field, value) => {
    setDraft((prev) => ({
      ...(prev || {}),
      games: {
        ...((prev || {}).games || {}),
        [key]: { ...(((prev || {}).games || {})[key] || {}), [field]: value },
      },
    }))
  }

  const patchParam = (key, field, value) => {
    setDraft((prev) => {
      const game = ((prev || {}).games || {})[key] || {}
      return {
        ...(prev || {}),
        games: {
          ...((prev || {}).games || {}),
          [key]: { ...game, params: { ...(game.params || {}), [field]: value } },
        },
      }
    })
  }

  const onSave = async () => {
    if (!draft) return
    setSaving(true)
    try {
      const next = await saveGamesSettings(draft)
      setData(next)
      setDraft(clone(next.settings))
      showToast('Игры сохранены. Бот уже читает новые числа.')
    } catch (err) {
      showToast(err.message || 'Не сохранилось', 'error')
    } finally {
      setSaving(false)
    }
  }

  const onResetGame = async (key) => {
    setSaving(true)
    try {
      const next = await resetGameSettings(key)
      setData(next)
      setDraft(clone(next.settings))
      showToast('Вернул игру к исходным числам')
    } catch (err) {
      showToast(err.message || 'Не сбросилось', 'error')
    } finally {
      setSaving(false)
    }
  }

  if (loading && !data) {
    return (
      <section className="grp-page nika-page gm-page">
        <div className="nika-skel" aria-hidden="true" />
      </section>
    )
  }

  const preview = current ? previewCommission(settings, current.key, pot, level) : null
  const payout = current ? previewPayout(current, currentState, pot) : null
  const currentStatus = statusOf(currentState)
  const flowGame = flowScope === 'all'
    ? {
        key: '_all',
        days: data?.series?.days || [],
        hours: data?.series?.hours || [],
        dayExtrema: data?.series?.dayExtrema,
        hourExtrema: data?.series?.hourExtrema,
        stats: { events: data?.totals?.events || 0, commission: data?.totals?.commission || 0, pot: data?.totals?.pot || 0 },
      }
    : current

  return (
    <section className={`grp-page nika-page gm-page${phone ? ' is-phone' : ' is-desktop'}`}>
      <header className="nika-head">
        <div className="nika-head-copy">
          <h1>Игры</h1>
          <p>Каждая игра — свой стол и своя аналитика. Числа живут в базе и не сбрасываются.</p>
        </div>
        <div className={`nika-status${currentState.maintenance ? ' is-hot' : settings.commission?.enabled ? ' is-ok' : ' is-hot'}`}>
          <b>{currentState.maintenance ? 'Техработы' : settings.commission?.enabled ? 'Комиссия жива' : 'Комиссия выключена'}</b>
          <span>{data?.totals?.on || 0} открыты · {data?.totals?.maintenance || 0} на паузе · {data?.totals?.off || 0} выкл</span>
        </div>
      </header>

      {dirty ? (
        <div className="gm-save" role="status">
          <div>
            <strong>Есть несохранённые правки</strong>
            <span>Бот ещё играет по старым числам. Поля ниже свободны — плашка их не закрывает.</span>
          </div>
          <div className="nika-card-actions">
            <button type="button" className="nika-btn" onClick={() => setDraft(clone(data.settings))}>Отменить</button>
            <button type="button" className="nika-btn nika-btn-primary" disabled={saving} onClick={onSave}>Сохранить</button>
          </div>
        </div>
      ) : null}

      <div className="nika-universe gm-uni">
        <article className="nika-uni">
          <p>Открыто</p>
          <strong><CountUp value={data?.totals?.on || 0} duration={700} /></strong>
          <small>из {games.length}</small>
        </article>
        <article className="nika-uni nika-uni-plus">
          <p>Собрано с игр</p>
          <strong><CountUp value={data?.totals?.commission || 0} duration={900} /></strong>
          <small>комиссия за всё время</small>
        </article>
        <article className="nika-uni">
          <p>Партий</p>
          <strong><CountUp value={data?.totals?.events || 0} duration={800} /></strong>
          <small>каждая честно записана</small>
        </article>
      </div>

      <nav className="nika-seg" role="tablist" aria-label="Разделы игр">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={`nika-seg-btn${tab === t.id ? ' is-on' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {phone ? t.short : t.label}
          </button>
        ))}
      </nav>

      {tab === 'catalog' && (
        <div className="nika-pane">
          <div className="nika-panel">
            <div className="nika-panel-top">
              <div>
                <h2>Все игры</h2>
                <p className="nika-help">Нажми карточку — откроется стол и аналитика этой игры.</p>
              </div>
              <div className="nika-seg nika-seg-mini" role="group" aria-label="Тип">
                <button type="button" className={`nika-seg-btn${kind === 'all' ? ' is-on' : ''}`} onClick={() => setKind('all')}>Все</button>
                <button type="button" className={`nika-seg-btn${kind === 'pve' ? ' is-on' : ''}`} onClick={() => setKind('pve')}>{phone ? 'Касса' : 'С кассой'}</button>
                <button type="button" className={`nika-seg-btn${kind === 'pvp' ? ' is-on' : ''}`} onClick={() => setKind('pvp')}>{phone ? 'Друг' : 'Друг на друга'}</button>
              </div>
            </div>
            <input
              className="nika-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Название, команда или настроение"
            />
            <div className="gm-grid nika-tables">
              {shown.map((g) => {
                const state = settings.games?.[g.key] || g.state || {}
                const st = statusOf(state)
                return (
                  <button
                    key={g.key}
                    type="button"
                    className={`gm-card nika-table${state.enabled ? '' : ' is-paused'}${state.maintenance ? ' is-dry' : ''}${selected === g.key ? ' is-on' : ''}`}
                    onClick={() => { setSelected(g.key); setTab('game') }}
                  >
                    <header>
                      <h3>{g.emoji} {g.title}</h3>
                      <span className={`nika-pill nika-pill-${st.tone === 'hot' ? 'mute' : st.tone}`}>{st.label}</span>
                    </header>
                    <p>{g.mood || g.hint}</p>
                    <p className="nika-bal-kicker">Собрано комиссией</p>
                    <strong className="nika-bal-value"><CountUp value={Number(g.stats?.commission) || 0} duration={700} /></strong>
                    <small>{cardChips(g, state).join(' · ')}</small>
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {tab === 'commission' && (
        <div className="nika-pane nika-stack">
          <section className="nika-panel">
            <h2>Комиссия всех игр</h2>
            <p className="nika-help">Один выключатель на весь стол. Процент зависит от ★ группы. Потом умножается на коэффициент конкретной игры.</p>
            <div className="nika-ios-list">
              <Switch
                on={!!settings.commission?.enabled}
                label="Брать комиссию"
                onClick={() => patchCommission('enabled', !settings.commission?.enabled)}
              />
              <div className="nika-ios-row is-static">
                <span>Минимальный банк</span>
                <b>{settings.commission?.minPot} кут</b>
              </div>
            </div>
            <Field label={`Минимум банка: ${settings.commission?.minPot || 0} кут`} help="Ниже этой суммы комиссия не берётся, чтобы копейки не округлялись в ноль.">
              <SliderNumber min={0} max={200} step={1} value={Number(settings.commission?.minPot || 0)} onChange={(v) => patchCommission('minPot', v)} />
            </Field>
          </section>
          <section className="nika-panel">
            <h2>Процент по ★ группы</h2>
            <p className="nika-help">Чем выше звезда, тем ниже комиссия. Это цена покупки уровня.</p>
            <div className="gm-rates">
              {[0, 1, 2, 3, 4, 5].map((lvl) => (
                <Field
                  key={lvl}
                  label={`${lvl}★ · ${pct(settings.commission?.rateByLevel?.[String(lvl)])}`}
                  help={lvl === 0 ? 'Группа без покупок' : lvl === 5 ? 'Максимум. Ниже не опускаем сами.' : ''}
                >
                  <SliderNumber
                    min={0}
                    max={40}
                    step={1}
                    value={Math.round(Number(settings.commission?.rateByLevel?.[String(lvl)] || 0) * 100)}
                    onChange={(v) => patchRate(lvl, v / 100)}
                  />
                </Field>
              ))}
            </div>
          </section>
        </div>
      )}

      {tab === 'game' && current && (
        <div className="nika-pane nika-stack">
          <section className="nika-panel">
            <div className="nika-panel-top">
              <div>
                <p className="nika-help" style={{ marginTop: 0 }}>{current.kind === 'pve' ? 'С кассой группы' : 'Игрок против игрока'}</p>
                <h2>{current.emoji} {current.title}</h2>
                <p className="nika-help">{current.mood || current.hint}</p>
                <p className="nika-id-line">
                  Команда: <Copyable value={current.command || current.key} label="команда">{current.command || current.key}</Copyable>
                </p>
              </div>
              <button type="button" className="nika-btn nika-btn-sm" disabled={saving} onClick={() => onResetGame(current.key)}>
                Как было
              </button>
            </div>
            <div className="nika-ios-list">
              <Switch
                on={!!currentState.enabled}
                label={currentState.enabled ? 'Игра включена' : 'Игра выключена'}
                onClick={() => patchGame(current.key, 'enabled', !currentState.enabled)}
              />
              <Switch
                on={!!currentState.maintenance}
                label={currentState.maintenance ? 'Технические работы' : 'Закрыть на техработы'}
                onClick={() => patchGame(current.key, 'maintenance', !currentState.maintenance)}
              />
              <div className="nika-ios-row is-static">
                <span>Собрано комиссией</span>
                <b>{fmt(current.stats?.commission || 0)}</b>
              </div>
              <div className="nika-ios-row is-static">
                <span>Статус</span>
                <b>{currentStatus.label}</b>
              </div>
            </div>
            <Field label={`Минимум: ${currentState.minBet} кут`} help="Ниже этой ставки партия не стартует.">
              <SliderNumber min={0} max={200} step={1} value={Number(currentState.minBet || 0)} onChange={(v) => patchGame(current.key, 'minBet', v)} />
            </Field>
            <Field label={`Максимум: ${fmt(currentState.maxBet)} кут`} help="Потолок самой игры. Лимит ★ группы может сузить ещё.">
              <SliderNumber
                min={10}
                max={current.kind === 'pvp' ? 500000 : 5000}
                step={current.kind === 'pvp' ? 1000 : 10}
                value={Number(currentState.maxBet || 0)}
                onChange={(v) => patchGame(current.key, 'maxBet', v)}
              />
            </Field>
            <Field label={`Комиссия этой игры: ×${Number(currentState.commissionMult || 0).toFixed(2)}`} help="0 — комиссии нет. 1 — как в таблице ★. Больше 1 — эта игра дороже.">
              <SliderNumber min={0} max={5} step={0.01} value={Number(currentState.commissionMult || 0)} onChange={(v) => patchGame(current.key, 'commissionMult', v)} />
            </Field>
          </section>

          {groupedFields.map((group) => (
            <section key={group.key} className="nika-panel gm-desk">
              <h2>{group.label}</h2>
              <p className="nika-help">
                {group.key === 'odds' && 'Эти числа крутят исход. Игрок их не видит, но чувствует.'}
                {group.key === 'payout' && 'Сколько касса отдаёт, если игрок угадал.'}
                {group.key === 'table' && 'Сколько людей или клеток на столе.'}
                {group.key === 'tempo' && 'Как быстро партия живёт и отвечает на нажатие.'}
              </p>
              {group.fields.map((field) => (
                <ParamField
                  key={field.key}
                  field={field}
                  value={currentState.params?.[field.key]}
                  onChange={(value) => patchParam(current.key, field.key, value)}
                />
              ))}
            </section>
          ))}

          <section className="nika-panel">
            <h2>Проверка числа</h2>
            <p className="nika-help">Считай до сохранения. Так видно, что увидит игрок в группе ★{level} при банке {fmt(pot)}.</p>
            <div className="gm-preview">
              <Field label={`Банк: ${fmt(pot)}`}>
                <SliderNumber min={10} max={2000} step={10} value={pot} onChange={setPot} />
              </Field>
              <Field label={`Уровень группы: ${level}★`}>
                <SliderNumber min={0} max={5} step={1} value={level} onChange={setLevel} />
              </Field>
            </div>
            <div className={`nika-flow-hero is-compact${payout ? ' is-three' : ''}`}>
              <div className="is-minus">
                <small>Комиссия</small>
                <b className="nika-minus">−{fmt(preview?.amount)}</b>
                <em>{preview?.note || `${pct(preview?.rate)} от банка`}</em>
              </div>
              <div className="is-plus">
                <small>Игроку после комиссии</small>
                <b className="nika-plus">{fmt(Math.max(0, pot - (preview?.amount || 0)))}</b>
                <em>если банк уходит победителю</em>
              </div>
              {payout ? (
                <div className="is-plus">
                  <small>{payout.label}</small>
                  <b className="nika-plus">{fmt(payout.value)}</b>
                  <em>до комиссии, при этой ставке</em>
                </div>
              ) : null}
            </div>
          </section>
        </div>
      )}

      {tab === 'flow' && flowGame && (
        <div className="nika-pane nika-stack nika-flow">
          <section className="nika-panel">
            <div className="nika-panel-top">
              <div>
                <h2>Аналитика {flowScope === 'all' ? 'всех игр' : current?.title}</h2>
                <p className="nika-help">Те же плюсы и минусы, что у Ники: оборот, комиссия, итог игрокам.</p>
              </div>
              <div className="nika-seg nika-seg-mini" role="group" aria-label="Охват">
                <button type="button" className={`nika-seg-btn${flowScope === 'game' ? ' is-on' : ''}`} onClick={() => setFlowScope('game')}>{phone ? 'Игра' : current?.title || 'Игра'}</button>
                <button type="button" className={`nika-seg-btn${flowScope === 'all' ? ' is-on' : ''}`} onClick={() => setFlowScope('all')}>Все</button>
              </div>
            </div>
            {flowScope === 'game' && (
              <div className="gm-flow-pick">
                {games.map((g) => (
                  <button
                    key={g.key}
                    type="button"
                    className={`nika-seg-btn${current?.key === g.key ? ' is-on' : ''}`}
                    onClick={() => setSelected(g.key)}
                  >
                    {g.emoji} {phone ? '' : g.title}
                  </button>
                ))}
              </div>
            )}
          </section>
          <GameAnalytics
            game={flowGame}
            range={range}
            onRange={setRange}
            dayFilter={dayFilter}
            onFilter={setDayFilter}
            phone={phone}
          />
        </div>
      )}

      {tab === 'journal' && (
        <div className="nika-pane">
          <section className="nika-panel">
            <h2>Что меняли</h2>
            <p className="nika-help">Последние сохранения. Каждое уже в базе и читается ботом.</p>
            <ul className="nika-ledger">
              {(data?.history || []).length === 0 && (
                <li className="nika-empty">Пока тишина. Первое сохранение появится здесь.</li>
              )}
              {(data?.history || []).map((row) => (
                <li key={row.id} className="nika-ledger-row">
                  <div>
                    <strong>Сохранение</strong>
                    <span>{when(row.createdAt)}</span>
                  </div>
                  <b>
                    <CopyableId value={row.adminId} />
                  </b>
                  <small>
                    {row.patch?.commission ? 'комиссия · ' : ''}
                    {row.patch?.games ? `игры ${Object.keys(row.patch.games).join(', ')}` : 'стол целиком'}
                  </small>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}

      {tab === 'machine' && (
        <div className="nika-pane nika-machine">
          <div className="nika-mach-grid">
            <article className="nika-mach-tile is-ok">
              <small>Кто видит</small>
              <b>Только создатель</b>
              <em>даже другой owner сюда не зайдёт</em>
            </article>
            <article className="nika-mach-tile">
              <small>Как доходит</small>
              <b>База → бот</b>
              <em>без перезапуска, за пару секунд</em>
            </article>
            <article className="nika-mach-tile">
              <small>Что трогает</small>
              <b>Каждую игру целиком</b>
              <em>выключатель, техработы, ставки, шансы, выплата</em>
            </article>
          </div>
          <section className="nika-panel">
            <h2>Как это устроено</h2>
            <ol className="gm-steps">
              <li>Техработы закрывают игру отдельно от выключателя. Игрок видит сообщение про работы, в «хелп игры» — короткую пометку.</li>
              <li>Выключатель игры. Если выключена — команда отвечает и партия не стартует.</li>
              <li>Минимум и максимум ставки. Лимит ★ группы может сузить максимум ещё, но не поднять его.</li>
              <li>Комиссия: сначала таблица по ★, потом множитель этой игры. Ноль множителя — комиссии нет.</li>
              <li>Шансы крутят скрытый исход: заклинивание, ноль, обвал, «домой», сорвавшаяся сделка.</li>
              <li>Выплата — сколько касса отдаёт, если игрок угадал. Стол — сколько людей или жил.</li>
              <li>Все числа пишутся в Postgres. Пустая запись один раз заполняется текущими значениями и больше сама не сбрасывается.</li>
            </ol>
          </section>
        </div>
      )}
    </section>
  )
}
