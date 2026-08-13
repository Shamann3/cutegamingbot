import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  fetchSoftRestartOverview,
  queueSoftRestartNow,
  saveSoftRestartPreset,
  saveSoftRestartSettings,
} from '../../lib/adminClient'
import { notifyAdmin } from '../../lib/notify'

const WEEKDAYS = [
  { id: 0, label: 'Пн' },
  { id: 1, label: 'Вт' },
  { id: 2, label: 'Ср' },
  { id: 3, label: 'Чт' },
  { id: 4, label: 'Пт' },
  { id: 5, label: 'Сб' },
  { id: 6, label: 'Вс' },
]

function fmtClock(totalSec) {
  const s = Math.max(0, Math.floor(Number(totalSec) || 0))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const r = s % 60
  const pad = (n) => String(n).padStart(2, '0')
  if (h > 0) return `${pad(h)}:${pad(m)}:${pad(r)}`
  return `${pad(m)}:${pad(r)}`
}

function fmtHuman(sec) {
  const s = Math.max(0, Math.floor(Number(sec) || 0))
  if (s < 60) return `${s}с`
  if (s < 3600) {
    const m = Math.floor(s / 60)
    const r = s % 60
    return r ? `${m}м ${r}с` : `${m}м`
  }
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return m ? `${h}ч ${m}м` : `${h}ч`
}

function fmtWhen(ts) {
  if (ts == null) return '—'
  const d = new Date(Number(ts) * 1000)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function SliderRow({ label, help, value, min, max, step = 1, onChange, display }) {
  const safe = Number.isFinite(Number(value)) ? Math.min(max, Math.max(min, Number(value))) : min
  const pct = ((safe - min) / (max - min || 1)) * 100
  return (
    <label className="sr-field">
      <div className="sr-field-top">
        <span className="sr-field-label">{label}</span>
        <span className="sr-field-value">{display ?? fmtHuman(safe)}</span>
      </div>
      {help ? <p className="sr-field-help">{help}</p> : null}
      <div className="sr-slider-wrap">
        <input className="sr-range" type="range" min={min} max={max} step={step} value={safe} style={{ '--sr-fill': `${pct}%` }} onChange={(e) => onChange(Number(e.target.value))} />
        <div className="sr-stepper">
          <button type="button" className="sr-step" onClick={() => onChange(Math.max(min, safe - step))}>−</button>
          <button type="button" className="sr-step" onClick={() => onChange(Math.min(max, safe + step))}>+</button>
        </div>
      </div>
    </label>
  )
}

function Toggle({ on, label, sub, onToggle }) {
  return (
    <button type="button" className={`sr-toggle${on ? ' sr-toggle-on' : ''}`} onClick={onToggle} aria-pressed={on}>
      <span className="sr-toggle-rail"><span className="sr-toggle-knob" /></span>
      <span className="sr-toggle-text">
        <strong>{label}</strong>
        {sub ? <small>{sub}</small> : null}
      </span>
    </button>
  )
}

function DocCard({ doc }) {
  if (!doc) return null
  return (
    <article className="sr-doc">
      <header className="sr-doc-head">
        <h4>{doc.title}</h4>
        <p>{doc.short}</p>
      </header>
      <p className="sr-doc-detail">{doc.detail}</p>
      {Array.isArray(doc.affects) && (
        <div className="sr-doc-block">
          <span className="sr-doc-label">Что меняется</span>
          <ul>{doc.affects.map((line) => <li key={line}>{line}</li>)}</ul>
        </div>
      )}
      {doc.code ? <div className="sr-doc-block"><span className="sr-doc-label">Код</span><code className="sr-doc-code">{doc.code}</code></div> : null}
    </article>
  )
}

export default function SoftRestartSection() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [cfg, setCfg] = useState(null)
  const [status, setStatus] = useState(null)
  const [diagnostics, setDiagnostics] = useState(null)
  const [docs, setDocs] = useState({})
  const [guide, setGuide] = useState(null)
  const [tab, setTab] = useState('howto')
  const [remain, setRemain] = useState(null)
  const [sinceLast, setSinceLast] = useState(null)
  const [diagOpen, setDiagOpen] = useState(false)
  const [timeDraft, setTimeDraft] = useState('04:00')
  const nextAtRef = useRef(null)
  const lastAtRef = useRef(null)
  const skewRef = useRef(0)

  const syncClocks = useCallback((st) => {
    setStatus(st || {})
    const serverNow = Number(st?.server_now) || Date.now() / 1000
    skewRef.current = serverNow - Date.now() / 1000
    if (st?.next_at != null) {
      nextAtRef.current = Number(st.next_at)
      setRemain(Math.max(0, Number(st.next_at) - serverNow))
    } else {
      nextAtRef.current = null
      setRemain(null)
    }
    if (st?.last_restart_at != null) {
      lastAtRef.current = Number(st.last_restart_at)
      setSinceLast(Math.max(0, serverNow - Number(st.last_restart_at)))
    } else {
      lastAtRef.current = null
      setSinceLast(null)
    }
  }, [])

  const applyPayload = useCallback((data) => {
    setCfg(data.config || {})
    setDocs(data.paramDocs || {})
    setGuide(data.guide || null)
    setDiagnostics(data.diagnostics || null)
    syncClocks(data.status || {})
  }, [syncClocks])

  const load = useCallback(async () => {
    try {
      applyPayload(await fetchSoftRestartOverview())
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    } finally {
      setLoading(false)
    }
  }, [applyPayload])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    let cancelled = false
    const tick = async () => {
      if (document.visibilityState !== 'visible') return
      try {
        const data = await fetchSoftRestartOverview()
        if (cancelled) return
        setDiagnostics(data.diagnostics || null)
        syncClocks(data.status || {})
      } catch { /* */ }
    }
    const id = setInterval(tick, 1200)
    return () => { cancelled = true; clearInterval(id) }
  }, [syncClocks])

  useEffect(() => {
    let raf = 0
    let last = 0
    const loop = (t) => {
      if (t - last > 200) {
        last = t
        const now = Date.now() / 1000 + skewRef.current
        if (nextAtRef.current == null) setRemain(null)
        else setRemain(Math.max(0, nextAtRef.current - now))
        if (lastAtRef.current == null) setSinceLast(null)
        else setSinceLast(Math.max(0, now - lastAtRef.current))
      }
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [])

  const patch = (key, value) => setCfg((prev) => ({ ...(prev || {}), [key]: value }))
  const patchCond = (key, value) => setCfg((prev) => ({
    ...(prev || {}),
    conditions: { ...((prev || {}).conditions || {}), [key]: value },
  }))

  const buildPayload = () => ({
    enabled: !!cfg.enabled,
    test: !!cfg.test,
    mode: String(cfg.mode || 'interval'),
    interval_sec: Number(cfg.interval_sec),
    initial_delay_sec: Number(cfg.initial_delay_sec),
    grace_sec: Number(cfg.grace_sec),
    timezone: String(cfg.timezone || 'Europe/Moscow'),
    hourly_minute: Number(cfg.hourly_minute || 0),
    daily_times: Array.isArray(cfg.daily_times) ? cfg.daily_times : [],
    weekdays: Array.isArray(cfg.weekdays) ? cfg.weekdays.map(Number) : [0, 1, 2, 3, 4, 5, 6],
    conditions: {
      min_uptime_sec: Number(cfg.conditions?.min_uptime_sec ?? 120),
      require_supervisor: !!cfg.conditions?.require_supervisor,
      max_restarts_per_day: Number(cfg.conditions?.max_restarts_per_day ?? 48),
      quiet_start: String(cfg.conditions?.quiet_start || ''),
      quiet_end: String(cfg.conditions?.quiet_end || ''),
    },
    notify_creator: cfg.notify_creator !== false,
  })

  const onSave = async () => {
    if (!cfg) return
    setSaving(true)
    try {
      await saveSoftRestartSettings(buildPayload())
      notifyAdmin('Сохранено · бот применит за ~1с')
      await load()
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    } finally {
      setSaving(false)
    }
  }

  const onPreset = async (name) => {
    setSaving(true)
    try {
      await saveSoftRestartPreset(name)
      notifyAdmin(`Пресет «${name}» применён`)
      await load()
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    } finally {
      setSaving(false)
    }
  }

  const onRestartNow = async () => {
    if (!window.confirm('Soft restart сейчас? В ЛС придёт короткое «ок», когда новый процесс встанет.')) return
    setSaving(true)
    try {
      await queueSoftRestartNow('panel')
      notifyAdmin('Команда рестарта отправлена')
      await load()
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    } finally {
      setSaving(false)
    }
  }

  const toggleDay = (id) => {
    const cur = new Set(Array.isArray(cfg.weekdays) ? cfg.weekdays.map(Number) : [])
    if (cur.has(id)) cur.delete(id)
    else cur.add(id)
    patch('weekdays', [...cur].sort((a, b) => a - b))
  }

  const addTime = () => {
    const t = String(timeDraft || '').trim()
    if (!/^\d{1,2}:\d{2}$/.test(t)) {
      notifyAdmin('Формат времени HH:MM', { error: true })
      return
    }
    const [hh, mm] = t.split(':').map(Number)
    if (hh > 23 || mm > 59) {
      notifyAdmin('Некорректное время', { error: true })
      return
    }
    const label = `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`
    const set = new Set(cfg.daily_times || [])
    set.add(label)
    patch('daily_times', [...set].sort())
  }

  const removeTime = (t) => {
    patch('daily_times', (cfg.daily_times || []).filter((x) => x !== t))
  }

  const pulse = useMemo(() => {
    if (!status?.alive) return status?.stale ? 'stale' : 'offline'
    if (status.requested) return 'restarting'
    if (status.block_reason) return 'blocked'
    if (cfg?.enabled) return 'armed'
    return 'idle'
  }, [status, cfg])

  if (loading || !cfg) {
    return (
      <article className="panel-shelf panel-shelf-page sr-page">
        <div className="sr-veil" />
        <p className="sr-kicker">Hidden layer</p>
        <h2 className="sr-title">Sypher</h2>
        <p className="sr-lead">Загрузка…</p>
      </article>
    )
  }

  const countdownActive = !!cfg.enabled && remain != null && status?.alive
  const mode = cfg.mode || 'interval'

  return (
    <article className="panel-shelf panel-shelf-page sr-page">
      <div className="sr-veil" />
      <div className="sr-scan" />

      <div className="sr-body">
      <header className="sr-hero">
        <p className="sr-kicker">Creator only · hidden side</p>
        <h2 className="sr-title">Sypher</h2>
        <p className="sr-lead">Полный контроль soft restart: режимы, времена суток, условия и живая телеметрия игрового бота. Прокручивай вниз — все настройки и инструкция ниже.</p>

        {!status?.alive && (
          <div className={`sr-banner${status?.stale ? ' sr-banner-stale' : ''}`}>
            <strong>{status?.stale ? 'Heartbeat устарел' : 'Бот не в сети'}</strong>
            <p>{diagnostics?.hint}</p>
            <ol>
              <li>Задеплой и перезапусти <b>игровой</b> <code>main.py</code>.</li>
              <li>Одна Postgres с API (<code>soft_restart_bridge</code>) или общий <code>data/sr_status.json</code>.</li>
            </ol>
            <button type="button" className="sr-btn sr-btn-ghost" onClick={() => setDiagOpen((v) => !v)}>
              {diagOpen ? 'Скрыть диагностику' : 'Диагностика bridge'}
            </button>
            {diagOpen && diagnostics && <pre className="sr-diag">{JSON.stringify(diagnostics, null, 2)}</pre>}
          </div>
        )}

        <div className={`sr-countdown sr-countdown-${pulse}`}>
          <div className="sr-countdown-ring"><span className="sr-countdown-glow" /></div>
          <div className="sr-countdown-body">
            <span className="sr-countdown-label">
              {!status?.alive ? (status?.stale ? 'heartbeat устарел' : 'бот не в сети')
                : status.requested ? 'идёт рестарт…'
                  : status.block_reason ? `блок: ${status.block_reason}`
                    : !cfg.enabled ? 'авто выключен'
                      : remain == null ? 'не в расписании'
                        : 'до следующего рестарта'}
            </span>
            <span className="sr-countdown-clock">{countdownActive ? fmtClock(remain) : '——:——'}</span>
            <span className="sr-countdown-meta">
              режим {status?.mode_label || mode}
              {countdownActive ? ` · ${fmtHuman(remain)}` : ''}
            </span>
          </div>
        </div>

        <div className="sr-stats">
          <div className="sr-stat"><span>pid</span><strong>{status?.pid ?? '—'}</strong></div>
          <div className="sr-stat"><span>аптайм pid</span><strong>{status?.uptime_sec != null ? fmtHuman(status.uptime_sec) : '—'}</strong></div>
          <div className="sr-stat"><span>с последнего</span><strong>{sinceLast != null ? fmtHuman(sinceLast) : '—'}</strong></div>
          <div className="sr-stat"><span>пульс</span><strong className={`sr-pulse-${pulse}`}>{pulse}</strong></div>
        </div>
        <div className="sr-stats" style={{ marginTop: '0.45rem' }}>
          <div className="sr-stat"><span>последний рестарт</span><strong>{fmtWhen(status?.last_restart_at)}</strong></div>
          <div className="sr-stat"><span>причина</span><strong>{status?.last_restart_reason || '—'}</strong></div>
          <div className="sr-stat"><span>сегодня</span><strong>{status?.restarts_today ?? 0}</strong></div>
          <div className="sr-stat"><span>handoff</span><strong>{status?.supervisor ? 'ON' : 'OFF'}</strong></div>
        </div>
      </header>

      <div className="sr-tabs" role="tablist">
        {[
          ['howto', 'Инструкция'],
          ['control', 'Управление'],
          ['schedule', 'Расписание'],
          ['conditions', 'Условия'],
          ['timeline', 'Таймлайн'],
          ['docs', 'Параметры и код'],
        ].map(([id, label]) => (
          <button key={id} type="button" className={`sr-tab${tab === id ? ' sr-tab-active' : ''}`} onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>

      <div className="sr-scroll">
        {tab === 'howto' && (
          <div className="sr-howto">
            <div className="sr-howto-card">
              <h3>Перед любыми действиями</h3>
              <ol>
                <li>Пульс сверху должен быть <b>armed / idle / blocked</b> — не <b>offline</b>. Иначе бот не связан с панелью.</li>
                <li>После правок всегда жми <b>Сохранить и применить</b> — иначе игровой бот не увидит настройки.</li>
                <li>Смотри отсчёт сверху и вкладку <b>Таймлайн</b>: там ближайшие слоты и история.</li>
              </ol>
            </div>

            <div className="sr-howto-card sr-howto-test">
              <h3>Как тестировать (безопасно)</h3>
              <p>Цель — убедиться, что рестарт проходит и в ЛС приходит короткое «ок», без боя по расписанию.</p>
              <ol>
                <li>Пресет <b>Test · авто OFF</b> (или тумблер «Авто» выкл).</li>
                <li>Вкладка <b>Условия</b>: мин. аптайм поставь <b>30–60с</b>, чтобы не ждать зря.</li>
                <li>Включи <b>ЛС после рестарта</b>.</li>
                <li><b>Сохранить</b> → кнопка <b>Рестарт сейчас</b>.</li>
                <li>Жди 10–40с: pid сменится, «с последнего» обнулится, в личку бота придёт <code>◈ soft restart · … · ок</code>.</li>
                <li>Проверь игру/кнопки после рестарта (lobby не должны «умирать»).</li>
              </ol>
              <div className="sr-howto-check">
                Быстрый тест по времени: Расписание → mode <b>interval</b>, интервал <b>120с</b>, пауза <b>60с</b>, мин. аптайм <b>30с</b> → Сохранить → смотри отсчёт. После проверки верни Live/Night.
              </div>
            </div>

            <div className="sr-howto-card sr-howto-live">
              <h3>Автоматические перезапуски (бой)</h3>
              <p>Выбери один режим и сохрани. Первый авто всегда не раньше «паузы после старта».</p>
              <ul>
                <li><b>Каждые N сек</b> — пресет Live или Расписание → interval (например 3600 = каждый час от аптайма).</li>
                <li><b>Каждый час по часам</b> — пресет Hourly или mode hourly, минута <code>:00</code> / <code>:15</code>…</li>
                <li><b>В конкретное время</b> — пресет Night или mode «По времени»: добавь <code>03:00</code>, <code>15:00</code>… + дни недели.</li>
              </ul>
              <ol>
                <li>Авто <b>ON</b>, тест <b>OFF</b>.</li>
                <li>Timezone обычно <code>Europe/Moscow</code>.</li>
                <li>Условия: мин. аптайм ≥ 120с, лимит/день с запасом, при необходимости тихие часы.</li>
                <li><b>Сохранить</b> → проверь Таймлайн (ближайшие слоты).</li>
                <li>После каждого авто в ЛС — одно короткое сообщение (если ЛС включено).</li>
              </ol>
              <div className="sr-howto-check">
                Если пульс <b>blocked: min_uptime</b> — это не ошибка: подожди аптайм или снизь порог в Условиях. Offline — перезапусти игровой <code>main.py</code> после деплоя.
              </div>
            </div>

            <div className="sr-howto-card">
              <h3>Что смотреть, что всё ок</h3>
              <ul>
                <li><b>до следующего</b> — живой таймер до авто.</li>
                <li><b>с последнего</b> / <b>последний рестарт</b> — факт, что рестарт был.</li>
                <li><b>сегодня</b> — сколько раз за день (лимит в Условиях).</li>
                <li><b>handoff ON</b> — rolling-рестарт без полного даунтайма.</li>
              </ul>
            </div>
          </div>
        )}

        {tab === 'control' && (
          <div className="sr-grid">
            <Toggle on={!!cfg.enabled} label="Авто-рестарт" sub={docs.enabled?.short} onToggle={() => patch('enabled', !cfg.enabled)} />
            <Toggle on={!!cfg.test} label="Тестовый режим" sub={docs.test?.short} onToggle={() => patch('test', !cfg.test)} />
            <Toggle on={cfg.notify_creator !== false} label="ЛС после рестарта" sub={docs.notify_creator?.short} onToggle={() => patch('notify_creator', cfg.notify_creator === false)} />

            <div className="sr-presets">
              <button type="button" className="sr-btn sr-btn-live" disabled={saving} onClick={() => onPreset('live')}>Live · каждый час (interval)</button>
              <button type="button" className="sr-btn sr-btn-ghost" disabled={saving} onClick={() => onPreset('hourly')}>Hourly · :00</button>
              <button type="button" className="sr-btn sr-btn-ghost" disabled={saving} onClick={() => onPreset('night')}>Night · 03:00</button>
              <button type="button" className="sr-btn sr-btn-ghost" disabled={saving} onClick={() => onPreset('test')}>Test · авто OFF</button>
              <button type="button" className="sr-btn sr-btn-danger" disabled={saving || !status?.alive} onClick={onRestartNow}>Рестарт сейчас</button>
            </div>
            <div className="sr-actions">
              <button type="button" className="sr-btn sr-btn-primary" disabled={saving} onClick={onSave}>{saving ? 'Сохраняю…' : 'Сохранить и применить'}</button>
              <button type="button" className="sr-btn sr-btn-ghost" disabled={saving} onClick={load}>Обновить</button>
            </div>
            <p className="sr-note">Не уверен с чего начать — открой вкладку <b>Инструкция</b> (тест и бой по шагам).</p>
          </div>
        )}

        {tab === 'schedule' && (
          <div className="sr-grid">
            <div className="sr-mode-row">
              {[
                ['interval', 'Каждые N сек'],
                ['hourly', 'Каждый час'],
                ['times', 'По времени'],
              ].map(([id, label]) => (
                <button key={id} type="button" className={`sr-mode${mode === id ? ' sr-mode-on' : ''}`} onClick={() => patch('mode', id)}>{label}</button>
              ))}
            </div>
            <p className="sr-field-help">{docs.mode?.detail}</p>

            <label className="sr-field">
              <div className="sr-field-top"><span className="sr-field-label">Timezone</span><span className="sr-field-value">{cfg.timezone}</span></div>
              <p className="sr-field-help">{docs.timezone?.short}</p>
              <input className="sr-text" value={cfg.timezone || 'Europe/Moscow'} onChange={(e) => patch('timezone', e.target.value)} />
            </label>

            <SliderRow label="Пауза после старта процесса" help={docs.initial_delay_sec?.detail} value={cfg.initial_delay_sec} min={30} max={21600} step={30} onChange={(n) => patch('initial_delay_sec', n)} />

            {mode === 'interval' && (
              <SliderRow label="Интервал между рестартами" help={docs.interval_sec?.detail} value={cfg.interval_sec} min={60} max={21600} step={60} onChange={(n) => patch('interval_sec', n)} />
            )}

            {mode === 'hourly' && (
              <SliderRow label="Минута часа (:MM)" help={docs.hourly_minute?.detail} value={cfg.hourly_minute ?? 0} min={0} max={59} step={1} display={`:${String(cfg.hourly_minute ?? 0).padStart(2, '0')}`} onChange={(n) => patch('hourly_minute', n)} />
            )}

            {mode === 'times' && (
              <>
                <div className="sr-field">
                  <div className="sr-field-top"><span className="sr-field-label">Времена дня</span></div>
                  <p className="sr-field-help">{docs.daily_times?.detail}</p>
                  <div className="sr-chips">
                    {(cfg.daily_times || []).map((t) => (
                      <button key={t} type="button" className="sr-chip" onClick={() => removeTime(t)}>{t} ×</button>
                    ))}
                  </div>
                  <div className="sr-time-add">
                    <input className="sr-text" value={timeDraft} onChange={(e) => setTimeDraft(e.target.value)} placeholder="HH:MM" />
                    <button type="button" className="sr-btn sr-btn-ghost" onClick={addTime}>Добавить</button>
                  </div>
                </div>
                <div className="sr-field">
                  <div className="sr-field-top"><span className="sr-field-label">Дни недели</span></div>
                  <p className="sr-field-help">{docs.weekdays?.short}</p>
                  <div className="sr-chips">
                    {WEEKDAYS.map((d) => (
                      <button key={d.id} type="button" className={`sr-chip${(cfg.weekdays || []).includes(d.id) ? ' sr-chip-on' : ''}`} onClick={() => toggleDay(d.id)}>{d.label}</button>
                    ))}
                  </div>
                </div>
              </>
            )}

            <SliderRow label="Grace (hard exit)" help={docs.grace_sec?.detail} value={cfg.grace_sec} min={0.5} max={30} step={0.5} display={`${Number(cfg.grace_sec).toFixed(1)}с`} onChange={(n) => patch('grace_sec', n)} />

            <div className="sr-actions">
              <button type="button" className="sr-btn sr-btn-primary" disabled={saving} onClick={onSave}>{saving ? 'Сохраняю…' : 'Применить расписание'}</button>
            </div>
          </div>
        )}

        {tab === 'conditions' && (
          <div className="sr-grid">
            <SliderRow label="Мин. аптайм перед авто" help={docs['conditions.min_uptime_sec']?.detail} value={cfg.conditions?.min_uptime_sec ?? 120} min={0} max={3600} step={10} onChange={(n) => patchCond('min_uptime_sec', n)} />
            <SliderRow label="Лимит рестартов / день" help={docs['conditions.max_restarts_per_day']?.detail} value={cfg.conditions?.max_restarts_per_day ?? 48} min={1} max={200} step={1} display={String(cfg.conditions?.max_restarts_per_day ?? 48)} onChange={(n) => patchCond('max_restarts_per_day', n)} />
            <Toggle on={!!cfg.conditions?.require_supervisor} label="Только с rolling handoff" sub={docs['conditions.require_supervisor']?.short} onToggle={() => patchCond('require_supervisor', !cfg.conditions?.require_supervisor)} />
            <label className="sr-field">
              <div className="sr-field-top"><span className="sr-field-label">Тихие часы</span></div>
              <p className="sr-field-help">Авто пропускается в окне start→end (можно через полночь). Пусто = выкл.</p>
              <div className="sr-time-add">
                <input className="sr-text" placeholder="start HH:MM" value={cfg.conditions?.quiet_start || ''} onChange={(e) => patchCond('quiet_start', e.target.value)} />
                <input className="sr-text" placeholder="end HH:MM" value={cfg.conditions?.quiet_end || ''} onChange={(e) => patchCond('quiet_end', e.target.value)} />
              </div>
            </label>
            <div className="sr-actions">
              <button type="button" className="sr-btn sr-btn-primary" disabled={saving} onClick={onSave}>Сохранить условия</button>
            </div>
          </div>
        )}

        {tab === 'timeline' && (
          <div className="sr-grid">
            <div className="sr-field">
              <div className="sr-field-top"><span className="sr-field-label">Ближайшие слоты</span></div>
              <div className="sr-timeline">
                {(status?.upcoming || []).length ? (status.upcoming || []).map((u) => (
                  <div key={`${u.at}-${u.label}`} className="sr-tl-row">
                    <strong>{u.label}</strong>
                    <span>через {fmtHuman(u.in_sec)}</span>
                  </div>
                )) : <p className="sr-note">Нет слотов (авто выкл или бот оффлайн).</p>}
              </div>
            </div>
            <div className="sr-field">
              <div className="sr-field-top"><span className="sr-field-label">История рестартов</span></div>
              <div className="sr-timeline">
                {(status?.history || []).length ? [...(status.history || [])].reverse().map((h, i) => (
                  <div key={`${h.at}-${i}`} className="sr-tl-row">
                    <strong>{fmtWhen(h.at)}</strong>
                    <span>{h.reason || h.source || '—'} · pid {h.pid ?? '—'}</span>
                  </div>
                )) : <p className="sr-note">Пока пусто — появится после первого soft restart с новым кодом.</p>}
              </div>
            </div>
          </div>
        )}

        {tab === 'docs' && (
          <div className="sr-docs">
            <p className="sr-note">Каждый параметр: смысл и что крутит в коде игрового бота. Листай вниз.</p>
            {Object.keys(docs).map((key) => <DocCard key={key} doc={docs[key]} />)}
            <button type="button" className="sr-btn sr-btn-ghost" onClick={() => setDiagOpen((v) => !v)}>
              {diagOpen ? 'Скрыть диагностику' : 'Диагностика bridge'}
            </button>
            {diagOpen && diagnostics && <pre className="sr-diag">{JSON.stringify(diagnostics, null, 2)}</pre>}
            {guide?.flow?.length ? (
              <div className="sr-howto-card" style={{ marginTop: '0.5rem' }}>
                <h3>{guide.title || 'Кратко'}</h3>
                <ol>{guide.flow.map((line) => <li key={line}>{line}</li>)}</ol>
              </div>
            ) : null}
          </div>
        )}
      </div>
      </div>
    </article>
  )
}
