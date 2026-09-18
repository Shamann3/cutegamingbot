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
import Copyable, { CopyableId, CopyableUsername } from '../../components/Copyable'
import NikaMoneyChart, { NikaSpark } from '../../components/NikaMoneyChart'
import { useIsPhone } from '../../lib/useIsDesktop'

const TABS = [
  { id: 'machine', label: 'Как работает' },
  { id: 'flow', label: 'Аналитика' },
  { id: 'incidents', label: 'Ошибки' },
  { id: 'groups', label: 'Группы' },
  { id: 'journal', label: 'Движения' },
  { id: 'settings', label: 'Система' },
]

const SPEED = [
  { id: 'auto', label: 'Авто' },
  { id: 'slow', label: 'Тихо' },
  { id: 'medium', label: 'Средне' },
  { id: 'aggressive', label: 'Жёстко' },
]

const THINK = [
  'Смотрит баланс каждой группы и сравнивает его с целью.',
  'Ниже цели — берёт куты из игр и касс, никогда не закрывает дыру одним разом.',
  'Выше цели — ждёт выдержку, потом часть уходит в копилку.',
  'Игроки этого не видят. Деньги двигает только бот.',
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

function ago(iso) {
  if (!iso) return 'проверки ещё не было'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const sec = Math.max(0, Math.round((Date.now() - d.getTime()) / 1000))
  if (sec < 60) return `${sec} сек назад`
  if (sec < 3600) return `${Math.floor(sec / 60)} мин назад`
  if (sec < 86400) return `${Math.floor(sec / 3600)} ч назад`
  return `${Math.floor(sec / 86400)} дн назад`
}

function toneOf(status) {
  if (status === 'done' || status === 'refunded') return 'ok'
  if (status === 'failed' || status === 'refund_failed') return 'bad'
  if (status === 'pending' || status === 'queued' || status === 'running') return 'wait'
  return 'mute'
}

function statusLabel(status) {
  if (status === 'done') return 'готово'
  if (status === 'refunded') return 'вернули'
  if (status === 'failed' || status === 'refund_failed') return 'сбой'
  if (status === 'queued') return 'ждёт'
  if (status === 'running' || status === 'pending') return 'сейчас'
  return status || '—'
}

function kindLabel(kind) {
  if (kind === 'sweep') return 'Сбор в копилку'
  if (kind === 'topup') return 'Долив группы'
  if (kind === 'revert') return 'Возврат'
  return kind || '—'
}

function cmdLabel(kind) {
  if (kind === 'force_tick') return 'Проверка'
  if (kind === 'force_topup') return 'Долив'
  if (kind === 'force_sweep') return 'Сбор'
  if (kind === 'revert') return 'Возврат'
  if (kind === 'retry_heal') return 'Повтор'
  if (kind === 'pause_all') return 'Выключение'
  if (kind === 'pause_group') return 'Пауза группы'
  if (kind === 'enable_group') return 'Группа включена'
  if (kind === 'resolve') return 'Закрыть'
  return kind || '—'
}

function forecastTone(action) {
  if (action === 'topup') return 'is-minus'
  if (action === 'sweep') return 'is-plus'
  if (action === 'blocked') return 'is-hot'
  if (action === 'watch') return 'is-warn'
  return 'is-mute'
}

function speedLabel(mode) {
  return SPEED.find((s) => s.id === mode)?.label || mode || 'Авто'
}

function cashTitle(src) {
  const t = String(src?.title || src?.sourceTitle || '')
  if (t === 'игры' || /комисс/i.test(t)) return 'Игры'
  if (t === 'фон' || /фонов/i.test(t)) return 'Фон'
  if (/рынок|дом/i.test(t)) return 'Дом игр'
  if (/копилк|прибыл/i.test(t)) return 'Копилка'
  return t || 'Касса'
}

function cashHint(src) {
  const t = String(src?.title || '')
  if (t === 'игры' || /комисс/i.test(t)) return 'комиссии с игр, первый источник долива'
  if (t === 'фон' || /фонов/i.test(t)) return 'фоновые заработки'
  if (/рынок|дом/i.test(t)) return 'дом игр'
  if (/копилк|прибыл/i.test(t)) return 'чистая прибыль, руками не снимаем'
  return 'касса для долива баланса групп'
}

function chatFlow(transfers, chatId) {
  const id = Number(chatId)
  let plus = 0
  let minus = 0
  for (const t of transfers || []) {
    if (t.status && t.status !== 'done') continue
    const amt = Number(t.amount) || 0
    const src = Number(t.sourceChatId)
    const dest = Number(t.destChatId)
    if (t.kind === 'sweep' && (src === id || dest === id)) plus += amt
    if (t.kind === 'topup' && (src === id || dest === id)) minus += amt
  }
  return { plus, minus, net: plus - minus }
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

function FlowStrip({ plus, minus, plusHint, minusHint, compact }) {
  const net = (Number(plus) || 0) - (Number(minus) || 0)
  return (
    <div className={`nika-flow-hero${compact ? ' is-compact' : ''}`}>
      <div className="is-plus">
        <small>Плюс</small>
        <b className="nika-plus"><CountUp value={Number(plus) || 0} duration={900} /></b>
        {plusHint ? <em>{plusHint}</em> : null}
      </div>
      <div className="is-minus">
        <small>Минус</small>
        <b className="nika-minus"><CountUp value={Number(minus) || 0} duration={900} /></b>
        {minusHint ? <em>{minusHint}</em> : null}
      </div>
      <div>
        <small>Итог</small>
        <b className={net >= 0 ? 'nika-plus' : 'nika-minus'}>
          <CountUp value={net} signed duration={900} />
        </b>
      </div>
    </div>
  )
}

function IdentityLine({ chatId, username, name, link }) {
  const uname = String(username || '').trim()
  return (
    <p className="nika-id-line">
      {name ? <span className="nika-id-name">{name}</span> : null}
      <CopyableId value={chatId} label="id группы" />
      {uname ? <CopyableUsername value={uname} label="username группы" /> : null}
      {link && /^https?:\/\//i.test(link) ? (
        <a className="nika-id-link" href={link} target="_blank" rel="noreferrer">ссылка</a>
      ) : null}
    </p>
  )
}

function GroupBalanceCard({ group, flow, extra }) {
  const gap = Number(group.gap) || 0
  return (
    <article className={`nika-table${group.starving ? ' is-dry' : ''}${group.enabled ? '' : ' is-paused'}`}>
      <header>
        <h3>{group.name}</h3>
        <span>{group.enabled ? speedLabel(group.speedMode) : 'пауза'}</span>
      </header>
      <IdentityLine chatId={group.chatId} username={group.username} link={group.link} />
      <p className="nika-bal-kicker">Баланс этой группы</p>
      <strong className="nika-bal-value"><CountUp value={Number(group.balance) || 0} duration={1000} /></strong>
      <div className="nika-bal-meta">
        <span>цель {fmt(group.target)}</span>
        <em className={gap > 0 ? 'nika-minus' : gap < 0 ? 'nika-plus' : 'nika-mute'}>
          {gap > 0 ? `не хватает ${fmt(gap)}` : gap < 0 ? `лишнее ${fmt(-gap)}` : 'в цели'}
        </em>
      </div>
      <FlowStrip
        compact
        plus={flow.plus}
        minus={flow.minus}
        plusHint="сбор в копилку"
        minusHint="долив баланса"
      />
      {extra}
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
  const [tab, setTab] = useState('machine')
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
  const transfers = data?.transfers || []
  const universe = earn?.universe || data?.universe || {}
  const chartPoints = range === 'hours' ? (earn?.hours || []) : (earn?.days || [])
  const extrema = range === 'hours' ? earn?.hourExtrema : earn?.extrema
  const sparkValues = (earn?.spark || []).map((s) => s.system)
  const vaultId = data?.meta?.sweepDestChatId || universe.vaultChatId
  const vaultFlow = chatFlow(transfers, vaultId)
  const dayRows = useMemo(() => {
    const rows = chartPoints.slice().reverse()
    if (dayFilter === 'plus') return rows.filter((d) => (d.net || 0) > 0)
    if (dayFilter === 'minus') return rows.filter((d) => (d.net || 0) < 0)
    return rows
  }, [chartPoints, dayFilter])
  const ledgerGroups = useMemo(
    () => groupLedger(transfers),
    [transfers],
  )
  const forecast = data?.forecast || {
    mode: data?.enabled ? (data?.dryRun ? 'dry' : 'live') : 'paused',
    summary: data?.enabled
      ? 'Считаю следующую проверку…'
      : 'Ника на паузе. Проверка смотрит цифры, но куты не двигает.',
    items: [],
  }
  const queued = Number(data?.commands?.queued || data?.commands?.pending || 0)
  const tickEvery = Number(data?.tickIntervalSec || data?.settings?.tickIntervalSec || 180)
  const recentMoves = transfers.slice(0, 6)
  const recentCmds = (data?.commandLog || []).slice(0, 6)
  const incidentCount = incidents.length + starving.length

  if (loading && !data) {
    return (
      <section className="grp-page nika-page">
        <div className="nika-skel" aria-hidden="true" />
      </section>
    )
  }

  const plusMinusHead = (
    <>
      <div className="nika-panel-top">
        <div>
          <h2>Плюсы и минусы</h2>
          <p className="nika-help">
            Плюс — сбор в копилку и комиссии игр. Минус — долив баланса групп из игр и касс.
            С {when(earn?.since)}.
          </p>
        </div>
        <div className="nika-seg nika-seg-mini" role="group" aria-label="Масштаб">
          <button type="button" className={`nika-seg-btn${range === 'days' ? ' is-on' : ''}`} onClick={() => { setRange('days'); setDayFilter('all') }}>Дни</button>
          <button type="button" className={`nika-seg-btn${range === 'hours' ? ' is-on' : ''}`} onClick={() => { setRange('hours'); setDayFilter('all') }}>Часы</button>
        </div>
      </div>
      <FlowStrip
        plus={earn?.nika?.plus || 0}
        minus={earn?.nika?.minus || 0}
        plusHint={`копилка ${fmt(earn?.nika?.sweptToVault)} · игры ${fmt(earn?.games?.commission)}`}
        minusHint="долив баланса групп"
      />
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
    </>
  )

  return (
    <section className={`grp-page nika-page${data?.crisis ? ' is-crisis' : ''}${phone ? ' is-phone' : ' is-desktop'}`}>
      <header className="nika-head">
        <div className="nika-head-copy">
          <h1>Ника</h1>
          <p>Сама держит баланс групп. Игроки этого не видят — только ты.</p>
        </div>
        <div className={`nika-status${data?.crisis ? ' is-hot' : data?.enabled ? ' is-ok' : ' is-off'}`}>
          <b>{data?.crisis ? 'Критично' : (data?.enabled ? (data?.dryRun ? 'Без движения' : 'Работает') : 'Пауза')}</b>
          <span>
            {data?.staleWorker
              ? 'бот молчит'
              : data?.lastTickAt
                ? ago(data.lastTickAt)
                : 'проверки ещё не было'}
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
            <span>{t.label}</span>
            {t.id === 'incidents' && incidentCount > 0 ? <i>{incidentCount}</i> : null}
          </button>
        ))}
      </nav>

      {tab === 'machine' && (
        <div className="nika-pane nika-machine">
          <div className="nika-mach-grid">
            <article className={`nika-mach-tile${data?.crisis ? ' is-hot' : data?.enabled ? ' is-ok' : ''}`}>
              <small>Режим</small>
              <b>{data?.crisis ? 'Критично' : (data?.enabled ? (data?.dryRun ? 'Без движения' : 'Боевой') : 'Пауза')}</b>
            </article>
            <article className="nika-mach-tile">
              <small>Проверка</small>
              <b>{data?.lastTickAt ? ago(data.lastTickAt) : 'ещё не было'}</b>
              <em>каждые {tickEvery} сек</em>
            </article>
            <article className={`nika-mach-tile${data?.staleWorker ? ' is-hot' : ''}`}>
              <small>Бот</small>
              <b>{data?.staleWorker ? 'молчит' : (data?.enabled ? 'жив' : 'ждёт включения')}</b>
            </article>
            <article className="nika-mach-tile">
              <small>Очередь</small>
              <b>{queued > 0 ? `${queued} команд` : 'пусто'}</b>
              <em>{groups.filter((g) => g.enabled).length} групп под Никой</em>
            </article>
          </div>

          <section className="nika-panel nika-panel-chart">
            {plusMinusHead}
          </section>

          <section className="nika-panel">
            <h2>Баланс групп</h2>
            <p className="nika-help">Сколько сейчас лежит в группе, чего не хватает до цели, и какие плюсы с минусами уже прошли.</p>
            <div className="nika-tables">
              {groups.length === 0 && (
                <article className="nika-empty">
                  <h3>Групп нет</h3>
                  <p>Поставь группу во вкладке «Группы» — Ника начнёт держать её баланс.</p>
                </article>
              )}
              {groups.map((g) => (
                <GroupBalanceCard key={g.chatId} group={g} flow={chatFlow(transfers, g.chatId)} />
              ))}
            </div>
          </section>

          <section className="nika-panel">
            <h2>Игры и кассы</h2>
            <p className="nika-help">Откуда Ника берёт куты на долив баланса групп. Копилка — последний источник и дом лишнего.</p>
            <div className="nika-tables">
              {ladder.map((src) => {
                const flow = chatFlow(transfers, src.chatId)
                return (
                  <article key={src.chatId} className={`nika-table${src.balance <= 0 ? ' is-dry' : ''}`}>
                    <header>
                      <h3>{cashTitle(src)}</h3>
                      <span>{src.balance <= 0 ? 'пусто' : 'есть куты'}</span>
                    </header>
                    <IdentityLine chatId={src.chatId} />
                    <p className="nika-bal-kicker">Баланс кассы</p>
                    <strong className="nika-bal-value"><CountUp value={Number(src.balance) || 0} duration={1000} /></strong>
                    <p className="nika-help">{cashHint(src)}</p>
                    <FlowStrip compact plus={flow.plus} minus={flow.minus} plusHint="пришло" minusHint="ушло на долив" />
                  </article>
                )
              })}
              <article className="nika-table nika-table-vault">
                <header>
                  <h3>Копилка</h3>
                  <span>чистая прибыль</span>
                </header>
                <IdentityLine chatId={vaultId} />
                <p className="nika-bal-kicker">Баланс копилки</p>
                <strong className="nika-bal-value nika-plus"><CountUp value={Number(universe.vault) || 0} duration={1000} /></strong>
                <FlowStrip
                  compact
                  plus={Number(earn?.nika?.sweptToVault) || vaultFlow.plus}
                  minus={vaultFlow.minus}
                  plusHint="сбор с групп"
                  minusHint="если брали отсюда"
                />
              </article>
            </div>
          </section>

          <section className="nika-panel">
            <div className="nika-panel-top">
              <div>
                <h2>Следующая проверка</h2>
                <p className="nika-help">{forecast.summary}</p>
              </div>
              <button type="button" className="nika-btn nika-btn-primary" disabled={!!busy} onClick={() => run({ action: 'force_tick' }, 'Проверка поставлена')}>
                Проверить сейчас
              </button>
            </div>
            {forecast.items?.length ? (
              <ul className="nika-next">
                {forecast.items.map((item) => (
                  <li key={item.chatId} className={forecastTone(item.action)}>
                    <b>{item.name}</b>
                    <span>{item.sourceTitle ? item.text.replace(item.sourceTitle, cashTitle({ title: item.sourceTitle })) : item.text}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="nika-help">
                {data?.enabled
                  ? 'Групп нет или баланс в зоне — проверка пройдёт вхолостую.'
                  : 'Включи автодолив в «Система», если хочешь, чтобы проверка двигала куты.'}
              </p>
            )}
          </section>

          <section className="nika-panel">
            <h2>Как думает</h2>
            <ol className="nika-think">
              {THINK.map((line, idx) => (
                <li key={line}>
                  <i>{idx + 1}</i>
                  <span>{line}</span>
                </li>
              ))}
            </ol>
          </section>

          <div className="nika-mach-split">
            <section className="nika-panel">
              <h2>Последние движения</h2>
              {recentMoves.length === 0 ? (
                <p className="nika-help">Ещё не было. Как только дольёт или соберёт — строка появится здесь.</p>
              ) : (
                <ul className="nika-moves">
                  {recentMoves.map((t) => (
                    <li key={t.id} className={t.sign > 0 ? 'is-plus' : t.sign < 0 ? 'is-minus' : ''}>
                      <div>
                        <b>{kindLabel(t.kind)}</b>
                        <span>{when(t.createdAt)}</span>
                      </div>
                      <strong>{t.sign < 0 ? '−' : t.sign > 0 ? '+' : ''}{fmt(t.amount)}</strong>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section className="nika-panel">
              <h2>Команды боту</h2>
              {recentCmds.length === 0 ? (
                <p className="nika-help">Очередь пуста. Кнопки «долить / проверить / вернуть» появляются здесь, пока бот их не заберёт.</p>
              ) : (
                <ul className="nika-moves">
                  {recentCmds.map((c) => (
                    <li key={c.id}>
                      <div>
                        <b>{cmdLabel(c.kind)}</b>
                        <span>{when(c.createdAt)}</span>
                      </div>
                      <em className={`nika-pill nika-pill-${toneOf(c.status)}`}>{statusLabel(c.status)}</em>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </div>
      )}

      {tab === 'flow' && (
        <div className="nika-pane nika-flow">
          <section className="nika-wallet">
            <div className="nika-wallet-top">
              <div>
                <p>Все балансы</p>
                <strong><CountUp value={Number(universe.system) || 0} duration={1400} /></strong>
                <span className="nika-wallet-eq">
                  игроки {fmt(universe.users)} + все чаты {fmt(universe.chats)}
                </span>
                <em className="nika-wallet-note">
                  Это сумма всех игроков и всех чатов. Баланс одной группы тут не обязан совпадать — он входит в «чаты».
                  Группы под Никой сейчас {fmt(universe.managed)}.
                </em>
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
                    <CopyableId value={h.chatId} label="id группы" />
                    <em>+{fmt(h.excess)}</em>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <div className="nika-universe">
            <UniCard label="Игроки" value={universe.users} hint="сумма балансов" />
            <UniCard label="Все чаты" value={universe.chats} hint="включая служебные" />
            <UniCard label="Все балансы" value={universe.system} hint="игроки + все чаты" tone="hero" />
            <UniCard label="Живые группы" value={universe.liveChats} hint="без служебных касс" />
            <UniCard label="Баланс групп" value={universe.managed} hint="под автодоливом" />
            <UniCard label="Копилка" value={universe.vault} hint="чистая прибыль" tone="plus" />
            <UniCard label="Игры и кассы" value={universe.ladder} hint="откуда доливаем" />
            <UniCard label="Лишнее" value={universe.excess} hint={`сверх ${fmt(universe.excessThreshold || 3000)}`} tone="warn" />
          </div>

          <section className="nika-panel nika-panel-chart">
            {plusMinusHead}

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
                      <em className={sys >= 0 ? 'nika-plus' : 'nika-minus'} title="Как сдвинулась сумма игроки+чаты">
                        сдвиг {signed(sys)}
                      </em>
                    ) : <em className="nika-mute">сдвиг —</em>}
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
              «Сдвиг» — как изменилась сумма игроки+все чаты за этот {range === 'hours' ? 'час' : 'день'}.
              Это не баланс одной группы. Пустые строки нарочно: так видно тишину.
            </p>
          </section>

          <section className="nika-panel">
            <h2>Игры и кассы</h2>
            <p className="nika-help">Откуда Ника берёт куты на долив баланса групп. Копилка — только вход, руками не снимаем.</p>
            <div className="nika-tables">
              {ladder.map((src) => {
                const flow = chatFlow(transfers, src.chatId)
                return (
                  <article key={src.chatId} className={`nika-table${src.balance <= 0 ? ' is-dry' : ''}`}>
                    <header>
                      <h3>{cashTitle(src)}</h3>
                      <span>{src.balance <= 0 ? 'пусто' : 'есть куты'}</span>
                    </header>
                    <IdentityLine chatId={src.chatId} />
                    <p className="nika-bal-kicker">Баланс кассы</p>
                    <strong className="nika-bal-value"><CountUp value={Number(src.balance) || 0} duration={1000} /></strong>
                    <p className="nika-help">{cashHint(src)}</p>
                    <FlowStrip compact plus={flow.plus} minus={flow.minus} plusHint="пришло" minusHint="ушло на долив" />
                  </article>
                )
              })}
            </div>
          </section>
        </div>
      )}

      {tab === 'incidents' && (
        <div className="nika-pane nika-stack">
          {incidents.length === 0 && !starving.length && (
            <article className="nika-empty">
              <h3>Тишина</h3>
              <p>Ника сама держит баланс групп. Карточка появится, только если автоматика уже пробовала и не смогла.</p>
            </article>
          )}
          {starving.map((g) => (
            <article key={`dry-${g.chatId}`} className="nika-card is-critical">
              <p className="nika-card-code">Нет кут</p>
              <h3>{g.name}</h3>
              <IdentityLine chatId={g.chatId} username={g.username} link={g.link} />
              <p>Баланс группы пуст: 0 из {fmt(g.target)}. Если в играх и кассах тоже ноль — доливать не из чего.</p>
              <div className="nika-card-actions">
                <button type="button" className="nika-btn nika-btn-primary" disabled={!!busy} onClick={() => run({ action: 'force_topup', chat_id: g.chatId }, 'Долив в очереди')}>Долить</button>
                <button type="button" className="nika-btn" disabled={!!busy} onClick={() => run({ action: 'force_tick' }, 'Проверяю')}>Проверить</button>
                <button type="button" className="nika-btn" disabled={!!busy} onClick={() => run({ action: 'pause_group', chat_id: g.chatId }, 'Группа на паузе')}>Пауза группы</button>
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
                    <span>
                      <CopyableId value={h.chatId} label="id группы" />
                      {h.username ? <> · <CopyableUsername value={h.username} /></> : null}
                      {' · '}{fmt(h.balance)} кут{h.forbidden ? ' · служебная' : ''}
                    </span>
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
                  showToast('Группа под Никой')
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
            {groups.map((g) => (
              <GroupBalanceCard
                key={g.chatId}
                group={g}
                flow={chatFlow(transfers, g.chatId)}
                extra={(
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
                          showToast('Сняли с Ники')
                          await load()
                        } catch (err) {
                          showToast(err.message || 'Не снялась', 'error')
                        }
                      }}
                    >
                      Снять
                    </button>
                  </div>
                )}
              />
            ))}
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
                    <small>
                      <Copyable value={t.sourceChatId} label="id">{t.sourceUsername ? `@${String(t.sourceUsername).replace(/^@/, '')}` : (t.sourceName || t.sourceChatId)}</Copyable>
                      {' → '}
                      <Copyable value={t.destChatId} label="id">{t.destUsername ? `@${String(t.destUsername).replace(/^@/, '')}` : (t.destName || t.destChatId)}</Copyable>
                      {' · '}
                      <CopyableId value={t.sourceChatId} />
                      {' → '}
                      <CopyableId value={t.destChatId} />
                    </small>
                    <em className={`nika-pill nika-pill-${toneOf(t.status)}`}>{statusLabel(t.status)}</em>
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
          {transfers.length === 0 && (
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
                  showToast(data?.dryRun ? 'Боевой режим' : 'Без движения кут')
                  await load()
                } catch (err) {
                  showToast(err.message || 'Не переключилась', 'error')
                }
              }}
            >
              <span>Без движения кут</span>
              <i className={`nika-switch${data?.dryRun ? ' is-on' : ''}`} />
            </button>
            <div className="nika-ios-row is-static">
              <span>Последняя проверка</span>
              <b>{when(data?.lastTickAt)}</b>
            </div>
            <div className="nika-ios-row is-static">
              <span>Журнал с</span>
              <b>{when(earn?.since || data?.settings?.earningsSince)}</b>
            </div>
            <div className="nika-ios-row is-static">
              <span>Удачных проверок подряд</span>
              <b>{data?.settings?.healOkStreak || 0}</b>
            </div>
          </div>
          <div className="nika-card-actions">
            <button type="button" className="nika-btn nika-btn-primary" disabled={!!busy} onClick={() => run({ action: 'force_tick' }, 'Проверка поставлена')}>Проверить сейчас</button>
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
