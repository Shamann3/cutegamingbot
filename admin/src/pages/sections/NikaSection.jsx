import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  fetchNikaEarnings,
  fetchNikaOverview,
  removeNikaGroup,
  runNikaAction,
  saveNikaGroup,
  saveNikaSettings,
  searchNikaCandidates,
} from '../../lib/adminClient'
import { showToast } from '../../components/ToastHost'
import CountUp from '../../components/CountUp'
import NikaMoneyChart, { NikaSpark } from '../../components/NikaMoneyChart'
import { useIsPhone } from '../../lib/useIsDesktop'

const TABS = [
  { id: 'flow', label: 'Аналитика' },
  { id: 'incidents', label: 'Ошибки' },
  { id: 'groups', label: 'Столы' },
  { id: 'journal', label: 'Движения' },
  { id: 'settings', label: 'Система' },
]

const SPEED = [
  { id: 'auto', label: 'Авто' },
  { id: 'slow', label: 'Тихо' },
  { id: 'medium', label: 'Средне' },
  { id: 'aggressive', label: 'Жёстко' },
]

function fmt(n) {
  return new Intl.NumberFormat('ru-RU').format(Number(n) || 0)
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
  return d.toLocaleString('ru-RU', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
  })
}

function dayTitle(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })
}

function toneOf(status) {
  if (status === 'done' || status === 'refunded') return 'ok'
  if (status === 'failed' || status === 'refund_failed') return 'bad'
  if (status === 'pending' || status === 'queued' || status === 'running') return 'wait'
  return 'mute'
}

function kindLabel(kind) {
  if (kind === 'sweep') return 'Сбор в копилку'
  if (kind === 'topup') return 'Долив стола'
  if (kind === 'revert') return 'Возврат'
  return kind || '—'
}

function UniCard({ label, value, hint, tone }) {
  return (
    <article className={`nika-uni${tone ? ` nika-uni-${tone}` : ''}`}>
      <p>{label}</p>
      <strong><CountUp value={Number(value) || 0} duration={1100} /></strong>
      {hint ? <small>{hint}</small> : null}
    </article>
  )
}

function groupLedger(rows) {
  const map = new Map()
  for (const t of rows) {
    const key = String(t.createdAt || '').slice(0, 10) || '—'
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(t)
  }
  return [...map.entries()]
}

export default function NikaSection() {
  const phone = useIsPhone()
  const [tab, setTab] = useState('flow')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [data, setData] = useState(null)
  const [earn, setEarn] = useState(null)
  const [range, setRange] = useState('days')
  const [dayFilter, setDayFilter] = useState('all')
  const [confirmStop, setConfirmStop] = useState(false)
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState([])
  const [draft, setDraft] = useState({ chatId: '', target: 5000, speed: 'auto' })
  const firstLoad = useRef(true)

  const applyPulse = useCallback((pulse, rest = {}) => {
    setData((prev) => ({
      ...(prev || {}),
      ...rest,
      ...(pulse || {}),
      settings: rest.settings || prev?.settings || {
        enabled: pulse?.enabled,
        dryRun: pulse?.dryRun,
      },
    }))
  }, [])

  const load = useCallback(async () => {
    try {
      const [overview, earnings] = await Promise.all([
        fetchNikaOverview(),
        fetchNikaEarnings().catch(() => null),
      ])
      setData(overview)
      setEarn(earnings)
      if (overview?.crisis && firstLoad.current) setTab('incidents')
      firstLoad.current = false
    } catch (err) {
      showToast(err.message || 'Ника не открылась', 'error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const id = window.setInterval(() => {
      if (document.visibilityState === 'visible') load()
    }, 12000)
    return () => window.clearInterval(id)
  }, [load])

  const run = useCallback(async (payload, okText) => {
    const key = `${payload.action}:${payload.incident_id || payload.chat_id || payload.transfer_id || 'x'}`
    setBusy(key)
    try {
      const res = await runNikaAction(payload)
      if (res.pulse) applyPulse(res.pulse)
      showToast(res.queuedId
        ? `${okText || 'Команда ушла боту'}`
        : (okText || 'Готово'))
      if (payload.action === 'pause_all') setConfirmStop(false)
      await load()
    } catch (err) {
      showToast(err.message || 'Не вышло', 'error')
    } finally {
      setBusy('')
    }
  }, [applyPulse, load])

  const incidents = useMemo(() => {
    const open = (data?.incidents || []).filter((i) => i.status === 'open' || i.status === 'ack')
    if (open.length) return open
    return (data?.incidentArchive || []).filter((i) => i.status !== 'resolved').slice(0, 12)
  }, [data])

  const starving = data?.starving || []
  const groups = data?.groups || []
  const ladder = data?.ladder || []
  const universe = earn?.universe || data?.universe || {}
  const chartPoints = range === 'hours' ? (earn?.hours || []) : (earn?.days || [])
  const extrema = range === 'hours' ? earn?.hourExtrema : earn?.extrema
  const plusDays = (earn?.days || []).filter((d) => (d.net || 0) > 0)
  const minusDays = (earn?.days || []).filter((d) => (d.net || 0) < 0)
  const sparkValues = (earn?.spark || []).map((s) => s.system)
  const ladderMax = Math.max(
    1,
    ...ladder.map((x) => Number(x.balance) || 0),
    Number(universe.vault) || 0,
  )
  const dayRows = useMemo(() => {
    const rows = chartPoints.slice().reverse()
    if (dayFilter === 'plus') return rows.filter((d) => (d.net || 0) > 0)
    if (dayFilter === 'minus') return rows.filter((d) => (d.net || 0) < 0)
    return rows
  }, [chartPoints, dayFilter])
  const ledgerGroups = useMemo(
    () => groupLedger(data?.transfers || []),
    [data],
  )

  const incidentCount = incidents.length + starving.length

  if (loading && !data) {
    return (
      <section className="grp-page nika-page">
        <div className="nika-skel" aria-hidden="true" />
      </section>
    )
  }

  return (
    <section className={`grp-page nika-page${data?.crisis ? ' is-crisis' : ''}${phone ? ' is-phone' : ' is-desktop'}`}>
      <header className="nika-head">
        <div className="nika-head-copy">
          <h1>Ника</h1>
          <p>
            Сама держит столы. Здесь живая картина всех балансов — как команда в личке —
            и плюсы с минусами по дням и часам.
          </p>
        </div>
        <div className={`nika-status${data?.crisis ? ' is-hot' : data?.enabled ? ' is-ok' : ' is-off'}`}>
          <b>{data?.crisis ? 'Критично' : (data?.enabled ? 'Работает' : 'Пауза')}</b>
          <span>
            {data?.staleWorker
              ? 'бот молчит'
              : data?.lastTickAt
                ? `тик ${when(data.lastTickAt)}`
                : 'тика ещё не было'}
          </span>
        </div>
      </header>

      {data?.crisis && (
        <div className="nika-alarm">
          <div>
            <strong>{data.headline || 'Большая проблема'}</strong>
            <p>{data.detail}</p>
          </div>
          <div className="nika-alarm-actions">
            <button type="button" className="nika-btn nika-btn-primary" disabled={!!busy} onClick={() => run({ action: 'force_tick' }, 'Проверяю снова')}>
              Проверить снова
            </button>
            {confirmStop ? (
              <button type="button" className="nika-btn nika-btn-danger" disabled={!!busy} onClick={() => run({ action: 'pause_all' }, 'Ника выключена')}>
                Точно выключить
              </button>
            ) : (
              <button type="button" className="nika-btn nika-btn-danger" onClick={() => setConfirmStop(true)}>
                Выключить Нику
              </button>
            )}
          </div>
        </div>
      )}

      <nav className="nika-seg" role="tablist" aria-label="Разделы Ники">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={`nika-seg-btn${tab === t.id ? ' is-on' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
            {t.id === 'incidents' && incidentCount > 0 ? <i>{incidentCount}</i> : null}
          </button>
        ))}
      </nav>

      {tab === 'flow' && (
        <div className="nika-pane nika-flow">
          <section className="nika-wallet">
            <div className="nika-wallet-top">
              <div>
                <p>Все балансы</p>
                <strong><CountUp value={Number(universe.system) || 0} duration={1400} /></strong>
                <span>игроки {fmt(universe.users)} + чаты {fmt(universe.chats)}</span>
              </div>
              <NikaSpark values={sparkValues} />
            </div>
            <div className="nika-wallet-meta">
              <b>нагрузка {Number(universe.pressurePct || 0).toFixed(1)}%</b>
              <span>{universe.hotGroups || 0} групп выше {fmt(universe.excessThreshold || 3000)}</span>
              <span>лишнее {fmt(universe.excess)}</span>
            </div>
            {(universe.hotList || []).length > 0 && (
              <ul className="nika-hot-list">
                {universe.hotList.map((h) => (
                  <li key={h.chatId}>
                    <span>{h.name}</span>
                    <em>+{fmt(h.excess)}</em>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <div className="nika-universe">
            <UniCard label="Игроки" value={universe.users} hint="сумма балансов" />
            <UniCard label="Все чаты" value={universe.chats} hint="включая кухню" />
            <UniCard label="Система" value={universe.system} hint="игроки + чаты" tone="hero" />
            <UniCard label="Живые группы" value={universe.liveChats} hint="без техкошельков" />
            <UniCard label="Столы Ники" value={universe.managed} hint="под автодоливом" />
            <UniCard label="Копилка" value={universe.vault} hint="чистая прибыль" tone="plus" />
            <UniCard label="Лестница" value={universe.ladder} hint="откуда доливаем" />
            <UniCard label="Лишнее" value={universe.excess} hint={`сверх ${fmt(universe.excessThreshold || 3000)}`} tone="warn" />
          </div>

          <section className="nika-panel nika-panel-chart">
            <div className="nika-panel-top">
              <div>
                <h2>Плюсы и минусы</h2>
                <p className="nika-help">
                  Плюс — сбор в копилку и комиссии игр. Минус — долив столов из лестницы.
                  С {when(earn?.since)}.
                </p>
              </div>
              <div className="nika-seg nika-seg-mini" role="group" aria-label="Масштаб">
                <button type="button" className={`nika-seg-btn${range === 'days' ? ' is-on' : ''}`} onClick={() => { setRange('days'); setDayFilter('all') }}>Дни</button>
                <button type="button" className={`nika-seg-btn${range === 'hours' ? ' is-on' : ''}`} onClick={() => { setRange('hours'); setDayFilter('all') }}>Часы</button>
              </div>
            </div>

            <div className="nika-flow-hero">
              <div className="is-plus">
                <small>Плюс</small>
                <b className="nika-plus"><CountUp value={earn?.nika?.plus || 0} duration={1200} /></b>
                <em>копилка {fmt(earn?.nika?.sweptToVault)} · игры {fmt(earn?.games?.commission)}</em>
              </div>
              <div className="is-minus">
                <small>Минус</small>
                <b className="nika-minus"><CountUp value={earn?.nika?.minus || 0} duration={1200} /></b>
                <em>долив столов</em>
              </div>
              <div>
                <small>Сальдо</small>
                <b className={(earn?.nika?.net || 0) >= 0 ? 'nika-plus' : 'nika-minus'}>
                  <CountUp value={earn?.nika?.net || 0} signed duration={1200} />
                </b>
                <em>{plusDays.length} дн. плюс · {minusDays.length} дн. минус</em>
              </div>
            </div>

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

            <NikaMoneyChart key={range} points={chartPoints} mode="system" />

            <div className="nika-seg nika-seg-mini nika-filter" role="group" aria-label="Фильтр знака">
              <button type="button" className={`nika-seg-btn${dayFilter === 'all' ? ' is-on' : ''}`} onClick={() => setDayFilter('all')}>Все</button>
              <button type="button" className={`nika-seg-btn${dayFilter === 'plus' ? ' is-on' : ''}`} onClick={() => setDayFilter('plus')}>Только плюсы</button>
              <button type="button" className={`nika-seg-btn${dayFilter === 'minus' ? ' is-on' : ''}`} onClick={() => setDayFilter('minus')}>Только минусы</button>
            </div>

            <ul className="nika-days">
              {dayRows.slice(0, phone ? 10 : 18).map((d) => {
                const sys = d.systemDelta
                return (
                  <li key={d.t} className={(d.net || 0) > 0 ? 'is-plus' : (d.net || 0) < 0 ? 'is-minus' : 'is-flat'}>
                    <i className="nika-days-pip" aria-hidden="true" />
                    <span className="nika-days-when">{d.label}</span>
                    <span className="nika-plus">+{fmt(d.plus)}</span>
                    <span className="nika-minus">−{fmt(d.minus)}</span>
                    <strong className={(d.net || 0) >= 0 ? 'nika-plus' : 'nika-minus'}>{signed(d.net)}</strong>
                    {sys != null ? (
                      <em className={sys >= 0 ? 'nika-plus' : 'nika-minus'} title="Изменение всех балансов">
                        все {signed(sys)}
                      </em>
                    ) : <em className="nika-mute">все —</em>}
                  </li>
                )
              })}
            </ul>
            {dayRows.length === 0 && (
              <p className="nika-help">
                {dayFilter === 'minus' ? 'Минусов на этом отрезке ещё не было.' : dayFilter === 'plus' ? 'Плюсов на этом отрезке ещё не было.' : 'Движений ещё нет.'}
              </p>
            )}
            <p className="nika-help">
              «Все» — как сдвинулась сумма игроки+чаты за этот {range === 'hours' ? 'час' : 'день'}.
              Пустые строки тоже нарочно: так видно, когда ничего не двигалось.
            </p>
          </section>

          <section className="nika-panel">
            <h2>Лестница</h2>
            <p className="nika-help">Откуда Ника берёт куты на долив. Копилка — только вход, руками не снимаем отсюда.</p>
            <div className="nika-ladder">
              {ladder.map((src) => {
                const fill = Math.min(100, ((Number(src.balance) || 0) / ladderMax) * 100)
                return (
                  <div key={src.chatId} className={`nika-src${src.balance <= 0 ? ' is-empty' : ''}`}>
                    <div className="nika-src-row">
                      <span>{src.title}</span>
                      <strong>{fmt(src.balance)}</strong>
                    </div>
                    <i className="nika-src-track"><i style={{ width: `${fill}%` }} /></i>
                  </div>
                )
              })}
              <div className="nika-src nika-src-vault">
                <div className="nika-src-row">
                  <span>Копилка</span>
                  <strong className="nika-plus">{fmt(universe.vault)}</strong>
                </div>
                <i className="nika-src-track"><i style={{ width: `${Math.min(100, ((Number(universe.vault) || 0) / ladderMax) * 100)}%` }} /></i>
              </div>
            </div>
          </section>
        </div>
      )}

      {tab === 'incidents' && (
        <div className="nika-pane nika-stack">
          {incidents.length === 0 && !starving.length && (
            <article className="nika-empty">
              <h3>Тишина</h3>
              <p>Ника сама держит столы. Карточка появится, только если автоматика уже пробовала и не смогла.</p>
            </article>
          )}
          {starving.map((g) => (
            <article key={`dry-${g.chatId}`} className="nika-card is-critical">
              <p className="nika-card-code">Нет кут</p>
              <h3>{g.name}</h3>
              <p>Стол пуст: 0 из {fmt(g.target)}. Если лестница тоже ноль — доливать не из чего.</p>
              <div className="nika-card-actions">
                <button type="button" className="nika-btn nika-btn-primary" disabled={!!busy} onClick={() => run({ action: 'force_topup', chat_id: g.chatId }, 'Долив в очереди')}>Долить</button>
                <button type="button" className="nika-btn" disabled={!!busy} onClick={() => run({ action: 'force_tick' }, 'Проверяю')}>Проверить</button>
                <button type="button" className="nika-btn" disabled={!!busy} onClick={() => run({ action: 'pause_group', chat_id: g.chatId }, 'Группа на паузе')}>Пауза стола</button>
              </div>
            </article>
          ))}
          {incidents.map((inc) => (
            <article key={inc.id} className={`nika-card is-${inc.severity || 'critical'}`}>
              <p className="nika-card-code">{inc.code} · ×{inc.occurrenceCount || 1} · {when(inc.updatedAt)}</p>
              <h3>{inc.title}</h3>
              <p className="nika-card-body">{inc.body}</p>
              <div className="nika-card-actions">
                {(inc.actions || []).map((a) => (
                  <button
                    key={a.id}
                    type="button"
                    title={a.hint}
                    className={`nika-btn${a.id === 'pause_all' ? ' nika-btn-danger' : ''}${['force_topup', 'retry_heal', 'revert'].includes(a.id) ? ' nika-btn-primary' : ''}`}
                    disabled={!!busy}
                    onClick={() => {
                      if (a.id === 'pause_all' && !confirmStop) {
                        setConfirmStop(true)
                        showToast('Нажми ещё раз, если точно выключаешь')
                        return
                      }
                      run({ action: a.id, incident_id: inc.id, chat_id: inc.chatId }, a.label)
                    }}
                  >
                    {a.label}
                  </button>
                ))}
                <button type="button" className="nika-btn" disabled={!!busy} onClick={() => run({ action: 'resolve', incident_id: inc.id }, 'Закрыто')}>
                  Закрыть
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      {tab === 'groups' && (
        <div className="nika-pane nika-stack">
          <div className="nika-add">
            <input
              className="nika-input"
              placeholder="id, @username или название"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={async (e) => {
                if (e.key !== 'Enter') return
                try {
                  setHits((await searchNikaCandidates(query)).items || [])
                } catch (err) {
                  showToast(err.message || 'Поиск не вышел', 'error')
                }
              }}
            />
            <button
              type="button"
              className="nika-btn"
              onClick={async () => {
                try {
                  setHits((await searchNikaCandidates(query)).items || [])
                } catch (err) {
                  showToast(err.message || 'Поиск не вышел', 'error')
                }
              }}
            >
              Найти
            </button>
          </div>
          {hits.length > 0 && (
            <ul className="nika-hits">
              {hits.map((h) => (
                <li key={h.chatId}>
                  <button type="button" className="nika-hit" disabled={h.forbidden} onClick={() => setDraft({ chatId: h.chatId, target: draft.target, speed: draft.speed })}>
                    <strong>{h.name}</strong>
                    <span>{h.chatId} · {fmt(h.balance)} кут{h.forbidden ? ' · кухня' : ''}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="nika-add">
            <input className="nika-input" placeholder="chat id" value={draft.chatId} onChange={(e) => setDraft((d) => ({ ...d, chatId: e.target.value }))} />
            <input className="nika-input nika-input-sm" inputMode="numeric" placeholder="цель" value={draft.target} onChange={(e) => setDraft((d) => ({ ...d, target: e.target.value }))} />
            <select className="nika-input nika-input-sm" value={draft.speed} onChange={(e) => setDraft((d) => ({ ...d, speed: e.target.value }))}>
              {SPEED.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
            <button
              type="button"
              className="nika-btn nika-btn-primary"
              disabled={!!busy}
              onClick={async () => {
                const chatId = Number(draft.chatId)
                const target = Number(draft.target)
                if (!chatId || !Number.isFinite(target)) {
                  showToast('Нужны id и цель', 'error')
                  return
                }
                try {
                  await saveNikaGroup({ chat_id: chatId, target_balance: target, speed_mode: draft.speed, enabled: true })
                  showToast('Стол под Никой')
                  setHits([])
                  await load()
                } catch (err) {
                  showToast(err.message || 'Не поставилась', 'error')
                }
              }}
            >
              Поставить
            </button>
          </div>

          <div className="nika-tables">
            {groups.map((g) => {
              const pct = g.target > 0 ? Math.min(140, Math.max(0, (g.balance / g.target) * 100)) : 0
              return (
                <article key={g.chatId} className={`nika-table${g.starving ? ' is-dry' : ''}${g.enabled ? '' : ' is-paused'}`}>
                  <header>
                    <h3>{g.name}</h3>
                    <span>{g.enabled ? 'живёт' : 'пауза'}</span>
                  </header>
                  <p className="nika-table-id">{g.chatId}</p>
                  <div className="nika-meter"><i style={{ width: `${Math.min(100, pct)}%` }} /></div>
                  <div className="nika-table-nums">
                    <b>{fmt(g.balance)}</b>
                    <span>цель {fmt(g.target)}</span>
                    <em className={g.gap > 0 ? 'nika-minus' : 'nika-plus'}>{signed(-g.gap)}</em>
                  </div>
                  <div className="nika-card-actions">
                    <button type="button" className="nika-btn nika-btn-primary" disabled={!!busy} onClick={() => run({ action: 'force_topup', chat_id: g.chatId }, 'Долив в очереди')}>Долить</button>
                    <button type="button" className="nika-btn" disabled={!!busy} onClick={() => run({ action: 'force_sweep', chat_id: g.chatId }, 'Сбор в очереди')}>Собрать</button>
                    <button type="button" className="nika-btn" disabled={!!busy} onClick={() => run({ action: g.enabled ? 'pause_group' : 'enable_group', chat_id: g.chatId }, g.enabled ? 'Пауза' : 'Включена')}>
                      {g.enabled ? 'Пауза' : 'Вкл'}
                    </button>
                    <button
                      type="button"
                      className="nika-btn"
                      onClick={async () => {
                        try {
                          await removeNikaGroup(g.chatId)
                          showToast('Сняли со стола')
                          await load()
                        } catch (err) {
                          showToast(err.message || 'Не снялась', 'error')
                        }
                      }}
                    >
                      Снять
                    </button>
                  </div>
                </article>
              )
            })}
          </div>
        </div>
      )}

      {tab === 'journal' && (
        <div className="nika-pane nika-stack">
          {ledgerGroups.map(([day, rows]) => (
            <div key={day} className="nika-ledger-group">
              <h3>{dayTitle(rows[0]?.createdAt)}</h3>
              <ul className="nika-ledger">
                {rows.map((t) => (
                  <li key={t.id} className={`nika-ledger-row is-${t.sign > 0 ? 'plus' : t.sign < 0 ? 'minus' : 'mute'}`}>
                    <div>
                      <strong>{kindLabel(t.kind)}</strong>
                      <span>{when(t.createdAt)}</span>
                    </div>
                    <b>{t.sign < 0 ? '−' : t.sign > 0 ? '+' : ''}{fmt(t.amount)}</b>
                    <small>{t.sourceChatId} → {t.destChatId}</small>
                    <em className={`nika-pill nika-pill-${toneOf(t.status)}`}>{t.status}</em>
                    {t.status === 'done' && !t.revertedAt ? (
                      <button type="button" className="nika-btn nika-btn-sm" disabled={!!busy} onClick={() => run({ action: 'revert', transfer_id: t.id }, 'Возврат в очереди')}>
                        Вернуть
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ))}
          {(data?.transfers || []).length === 0 && (
            <article className="nika-empty">
              <h3>Движений ещё нет</h3>
              <p>Как только Ника дольёт или соберёт куты, строка появится здесь со знаком плюс или минус.</p>
            </article>
          )}
        </div>
      )}

      {tab === 'settings' && (
        <div className="nika-pane nika-stack">
          <div className="nika-ios-list">
            <button
              type="button"
              className="nika-ios-row"
              onClick={async () => {
                try {
                  const pulse = await saveNikaSettings({ enabled: !data?.enabled })
                  applyPulse(pulse)
                  showToast(data?.enabled ? 'Ника на паузе' : 'Ника включена')
                  await load()
                } catch (err) {
                  showToast(err.message || 'Не переключилась', 'error')
                }
              }}
            >
              <span>Автодолив</span>
              <i className={`nika-switch${data?.enabled ? ' is-on' : ''}`} />
            </button>
            <button
              type="button"
              className="nika-ios-row"
              onClick={async () => {
                try {
                  const pulse = await saveNikaSettings({ dry_run: !data?.dryRun })
                  applyPulse(pulse)
                  showToast(data?.dryRun ? 'Боевой режим' : 'Сухой прогон')
                  await load()
                } catch (err) {
                  showToast(err.message || 'Не переключилась', 'error')
                }
              }}
            >
              <span>Сухой прогон</span>
              <i className={`nika-switch${data?.dryRun ? ' is-on' : ''}`} />
            </button>
            <div className="nika-ios-row is-static">
              <span>Последний тик</span>
              <b>{when(data?.lastTickAt)}</b>
            </div>
            <div className="nika-ios-row is-static">
              <span>Журнал с</span>
              <b>{when(earn?.since || data?.settings?.earningsSince)}</b>
            </div>
            <div className="nika-ios-row is-static">
              <span>Серия тиков</span>
              <b>{data?.settings?.healOkStreak || 0}</b>
            </div>
          </div>
          <div className="nika-card-actions">
            <button type="button" className="nika-btn nika-btn-primary" disabled={!!busy} onClick={() => run({ action: 'force_tick' }, 'Тик поставлен')}>Принудительный тик</button>
            <button type="button" className="nika-btn" disabled={!!busy} onClick={() => run({ action: 'retry_heal' }, 'Самолечение ещё раз')}>Повторить лечение</button>
          </div>
          {data?.settings?.lastError ? (
            <p className="nika-error-line">{data.settings.lastError}</p>
          ) : (
            <p className="nika-help">Внутренних ошибок нет. Ника молчит в чатах игроков — только ты это видишь.</p>
          )}
        </div>
      )}
    </section>
  )
}
