import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  fetchSoftRestartOverview,
  queueSoftRestartNow,
  saveSoftRestartPreset,
  saveSoftRestartSettings,
} from '../../lib/adminClient'
import { notifyAdmin } from '../../lib/notify'

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

function SliderRow({ label, help, value, min, max, step = 1, onChange, display }) {
  const safe = Number.isFinite(Number(value))
    ? Math.min(max, Math.max(min, Number(value)))
    : min
  const pct = ((safe - min) / (max - min || 1)) * 100
  return (
    <label className="sr-field">
      <div className="sr-field-top">
        <span className="sr-field-label">{label}</span>
        <span className="sr-field-value">{display ?? fmtHuman(safe)}</span>
      </div>
      {help ? <p className="sr-field-help">{help}</p> : null}
      <div className="sr-slider-wrap">
        <input
          className="sr-range"
          type="range"
          min={min}
          max={max}
          step={step}
          value={safe}
          style={{ '--sr-fill': `${pct}%` }}
          onChange={(e) => onChange(Number(e.target.value))}
        />
        <div className="sr-stepper">
          <button type="button" className="sr-step" onClick={() => onChange(Math.max(min, safe - step))} aria-label="меньше">−</button>
          <button type="button" className="sr-step" onClick={() => onChange(Math.min(max, safe + step))} aria-label="больше">+</button>
        </div>
      </div>
    </label>
  )
}

function Toggle({ on, label, sub, onToggle }) {
  return (
    <button
      type="button"
      className={`sr-toggle${on ? ' sr-toggle-on' : ''}`}
      onClick={onToggle}
      aria-pressed={on}
    >
      <span className="sr-toggle-rail" aria-hidden="true">
        <span className="sr-toggle-knob" />
      </span>
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
      {Array.isArray(doc.affects) && doc.affects.length > 0 && (
        <div className="sr-doc-block">
          <span className="sr-doc-label">Что меняется в рантайме</span>
          <ul>
            {doc.affects.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      )}
      {doc.code ? (
        <div className="sr-doc-block">
          <span className="sr-doc-label">Код</span>
          <code className="sr-doc-code">{doc.code}</code>
        </div>
      ) : null}
    </article>
  )
}

export default function SoftRestartSection() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [cfg, setCfg] = useState(null)
  const [status, setStatus] = useState(null)
  const [diagnostics, setDiagnostics] = useState(null)
  const [help, setHelp] = useState({})
  const [docs, setDocs] = useState({})
  const [guide, setGuide] = useState(null)
  const [tab, setTab] = useState('control')
  const [remain, setRemain] = useState(null)
  const [diagOpen, setDiagOpen] = useState(false)
  const nextAtRef = useRef(null)
  const skewRef = useRef(0)

  const syncStatusClock = useCallback((st) => {
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
  }, [])

  const applyPayload = useCallback((data) => {
    setCfg(data.config || {})
    setHelp(data.paramHelp || {})
    setDocs(data.paramDocs || {})
    setGuide(data.guide || null)
    setDiagnostics(data.diagnostics || null)
    syncStatusClock(data.status || {})
  }, [syncStatusClock])

  const load = useCallback(async () => {
    try {
      const data = await fetchSoftRestartOverview()
      applyPayload(data)
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
        syncStatusClock(data.status || {})
        // подтянуть applied с бота, не затирая локальные несохранённые правки
        if (data.config && !saving) {
          // не трогаем cfg здесь
        }
      } catch {
        /* тихо */
      }
    }
    const id = setInterval(tick, 1200)
    return () => { cancelled = true; clearInterval(id) }
  }, [syncStatusClock, saving])

  useEffect(() => {
    let raf = 0
    let last = 0
    const loop = (t) => {
      if (t - last > 200) {
        last = t
        const nextAt = nextAtRef.current
        if (nextAt == null) setRemain(null)
        else {
          const now = Date.now() / 1000 + skewRef.current
          setRemain(Math.max(0, nextAt - now))
        }
      }
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [])

  const patch = (key, value) => {
    setCfg((prev) => ({ ...(prev || {}), [key]: value }))
  }

  const onSave = async () => {
    if (!cfg) return
    setSaving(true)
    try {
      const res = await saveSoftRestartSettings({
        enabled: !!cfg.enabled,
        test: !!cfg.test,
        interval_sec: Number(cfg.interval_sec),
        initial_delay_sec: Number(cfg.initial_delay_sec),
        grace_sec: Number(cfg.grace_sec),
      })
      if (res.config) setCfg(res.config)
      if (res.status) syncStatusClock(res.status)
      notifyAdmin('Сохранено · бот подхватит за ~1с')
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
      notifyAdmin(name === 'live' ? 'Preset Live применён' : 'Preset Test применён')
      await load()
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    } finally {
      setSaving(false)
    }
  }

  const onRestartNow = async () => {
    if (!window.confirm('Запустить soft restart сейчас? В ЛС придёт короткое «ок», когда новый процесс встанет.')) {
      return
    }
    setSaving(true)
    try {
      const res = await queueSoftRestartNow('panel')
      notifyAdmin(
        res?.pg_ok || (res?.files || []).length
          ? 'Команда рестарта отправлена боту'
          : 'Команда записана, но bridge может быть недоступен — смотри диагностику',
      )
      await load()
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    } finally {
      setSaving(false)
    }
  }

  const pulse = useMemo(() => {
    if (!status?.alive) return status?.stale ? 'stale' : 'offline'
    if (status.requested) return 'restarting'
    if (cfg?.enabled) return 'armed'
    return 'idle'
  }, [status, cfg])

  const synced = useMemo(() => {
    const a = status?.applied
    if (!a || !cfg) return false
    return (
      !!a.enabled === !!cfg.enabled
      && !!a.test === !!cfg.test
      && Number(a.interval_sec) === Number(cfg.interval_sec)
      && Number(a.initial_delay_sec) === Number(cfg.initial_delay_sec)
      && Number(a.grace_sec) === Number(cfg.grace_sec)
    )
  }, [status, cfg])

  if (loading || !cfg) {
    return (
      <article className="panel-shelf panel-shelf-page sr-page">
        <div className="sr-veil" aria-hidden="true" />
        <p className="sr-kicker">Hidden layer</p>
        <h2 className="sr-title">Sypher</h2>
        <p className="sr-lead">Загрузка скрытого контура…</p>
      </article>
    )
  }

  const autoOn = !!cfg.enabled
  const countdownActive = autoOn && remain != null && status?.alive

  return (
    <article className="panel-shelf panel-shelf-page sr-page">
      <div className="sr-veil" aria-hidden="true" />
      <div className="sr-scan" aria-hidden="true" />

      <header className="sr-hero">
        <p className="sr-kicker">Creator only · hidden side</p>
        <h2 className="sr-title">Sypher</h2>
        <p className="sr-lead">
          {guide?.subtitle || 'Мягкий перезапуск процесса. Каждый параметр ниже описан: что делает и какой код крутит.'}
        </p>

        {!status?.alive && (
          <div className={`sr-banner${status?.stale ? ' sr-banner-stale' : ''}`}>
            <strong>{status?.stale ? 'Heartbeat устарел' : 'Бот не в сети'}</strong>
            <p>{diagnostics?.hint}</p>
            <ol>
              <li>Задеплой и перезапусти <b>игровой</b> процесс (<code>main.py</code> / entrypoint бота), не admin-bot.</li>
              <li>API и бот должны смотреть в <b>одну Postgres</b> (таблица <code>soft_restart_bridge</code>) либо общий <code>data/sr_status.json</code>.</li>
              <li>После старта пульс станет <b>armed/idle</b> за 1–2 секунды.</li>
            </ol>
            <button type="button" className="sr-btn sr-btn-ghost" onClick={() => setDiagOpen((v) => !v)}>
              {diagOpen ? 'Скрыть диагностику' : 'Показать диагностику bridge'}
            </button>
            {diagOpen && diagnostics && (
              <pre className="sr-diag">{JSON.stringify(diagnostics, null, 2)}</pre>
            )}
          </div>
        )}

        <div className={`sr-countdown sr-countdown-${pulse}`}>
          <div className="sr-countdown-ring" aria-hidden="true">
            <span className="sr-countdown-glow" />
          </div>
          <div className="sr-countdown-body">
            <span className="sr-countdown-label">
              {!status?.alive
                ? (status?.stale ? 'heartbeat устарел' : 'бот не в сети')
                : !autoOn
                  ? 'авто выключен'
                  : status.requested
                    ? 'идёт рестарт…'
                    : remain == null
                      ? 'ещё не в расписании'
                      : 'до следующего рестарта'}
            </span>
            <span className="sr-countdown-clock" key={countdownActive ? Math.floor(remain) : pulse}>
              {countdownActive ? fmtClock(remain) : '——:——'}
            </span>
            <span className="sr-countdown-meta">
              {countdownActive
                ? fmtHuman(remain)
                : status?.alive
                  ? (synced ? 'конфиг синхронизирован с ботом' : 'есть несохранённые/неприменённые правки')
                  : (diagnostics?.hint || 'нет heartbeat')}
            </span>
          </div>
        </div>

        <div className="sr-stats">
          <div className="sr-stat">
            <span>pid</span>
            <strong>{status?.pid ?? '—'}</strong>
          </div>
          <div className="sr-stat">
            <span>аптайм</span>
            <strong>{status?.uptime_sec != null ? fmtHuman(status.uptime_sec) : '—'}</strong>
          </div>
          <div className="sr-stat">
            <span>handoff</span>
            <strong>{status?.supervisor ? 'ON' : 'OFF'}</strong>
          </div>
          <div className="sr-stat">
            <span>пульс</span>
            <strong className={`sr-pulse-${pulse}`}>{pulse}</strong>
          </div>
        </div>
      </header>

      <div className="sr-tabs" role="tablist">
        {[
          ['control', 'Управление'],
          ['timing', 'Таймеры'],
          ['docs', 'Параметры и код'],
          ['guide', 'Как это работает'],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`sr-tab${tab === id ? ' sr-tab-active' : ''}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="sr-scroll">
        {tab === 'control' && (
          <div className="sr-grid">
            <Toggle
              on={!!cfg.enabled}
              label={docs.enabled?.title || 'Авто-рестарт'}
              sub={docs.enabled?.short || help.enabled}
              onToggle={() => patch('enabled', !cfg.enabled)}
            />
            <Toggle
              on={!!cfg.test}
              label={docs.test?.title || 'Тестовый режим'}
              sub={docs.test?.short || help.test}
              onToggle={() => patch('test', !cfg.test)}
            />

            <div className="sr-presets">
              <button type="button" className="sr-btn sr-btn-live" disabled={saving} onClick={() => onPreset('live')}>
                Preset Live
              </button>
              <button type="button" className="sr-btn sr-btn-ghost" disabled={saving} onClick={() => onPreset('test')}>
                Preset Test
              </button>
              <button type="button" className="sr-btn sr-btn-danger" disabled={saving || !status?.alive} onClick={onRestartNow}>
                Рестарт сейчас
              </button>
            </div>

            <div className="sr-actions">
              <button type="button" className="sr-btn sr-btn-primary" disabled={saving} onClick={onSave}>
                {saving ? 'Сохраняю…' : 'Сохранить и применить'}
              </button>
              <button type="button" className="sr-btn sr-btn-ghost" disabled={saving} onClick={load}>
                Обновить
              </button>
            </div>

            <p className="sr-note">
              Live = авто ON + тест OFF. Test = авто OFF + тест ON.
              После рестарта в личку бота придёт одно короткое
              {' '}<code>◈ soft restart · … · ок</code>.
              Подробности влияния на код — вкладка «Параметры и код».
            </p>
          </div>
        )}

        {tab === 'timing' && (
          <div className="sr-grid">
            <SliderRow
              label={docs.initial_delay_sec?.title || 'Пауза до первого рестарта'}
              help={docs.initial_delay_sec?.detail || help.initial_delay_sec}
              value={cfg.initial_delay_sec}
              min={30}
              max={21600}
              step={30}
              onChange={(n) => patch('initial_delay_sec', n)}
            />
            <SliderRow
              label={docs.interval_sec?.title || 'Интервал между рестартами'}
              help={docs.interval_sec?.detail || help.interval_sec}
              value={cfg.interval_sec}
              min={60}
              max={21600}
              step={60}
              onChange={(n) => patch('interval_sec', n)}
            />
            <SliderRow
              label={docs.grace_sec?.title || 'Grace (жёсткий выход)'}
              help={docs.grace_sec?.detail || help.grace_sec}
              value={cfg.grace_sec}
              min={0.5}
              max={30}
              step={0.5}
              display={`${Number(cfg.grace_sec).toFixed(1)}с`}
              onChange={(n) => patch('grace_sec', n)}
            />
            <div className="sr-actions">
              <button type="button" className="sr-btn sr-btn-primary" disabled={saving} onClick={onSave}>
                {saving ? 'Сохраняю…' : 'Применить таймеры'}
              </button>
            </div>
          </div>
        )}

        {tab === 'docs' && (
          <div className="sr-docs">
            <p className="sr-note">
              Ниже — каждый параметр: смысл, что меняется в рантайме и какой файл/функции это крутят.
            </p>
            {['enabled', 'test', 'initial_delay_sec', 'interval_sec', 'grace_sec'].map((key) => (
              <DocCard key={key} doc={docs[key]} />
            ))}
          </div>
        )}

        {tab === 'guide' && (
          <div className="sr-guide">
            <h3>{guide?.title || 'Скрытый Soft Restart'}</h3>
            <ol>
              {(guide?.flow || []).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ol>
            <p className="sr-note" style={{ marginTop: '0.85rem' }}>
              Команды в личке (<code>.r</code>, <code>sypherrestart</code>) остаются как запасной канал.
              Основная настройка — эта вкладка.
            </p>
            {status?.alive && (
              <button type="button" className="sr-btn sr-btn-ghost" style={{ marginTop: '0.75rem' }} onClick={() => setDiagOpen((v) => !v)}>
                {diagOpen ? 'Скрыть диагностику' : 'Диагностика bridge'}
              </button>
            )}
            {diagOpen && diagnostics && (
              <pre className="sr-diag">{JSON.stringify(diagnostics, null, 2)}</pre>
            )}
          </div>
        )}
      </div>
    </article>
  )
}
