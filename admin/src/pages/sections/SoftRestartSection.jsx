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

function SliderRow({
  label,
  help,
  value,
  min,
  max,
  step = 1,
  onChange,
  display,
}) {
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

export default function SoftRestartSection() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [cfg, setCfg] = useState(null)
  const [status, setStatus] = useState(null)
  const [help, setHelp] = useState({})
  const [guide, setGuide] = useState(null)
  const [tab, setTab] = useState('control')
  const [remain, setRemain] = useState(null)
  const nextAtRef = useRef(null)
  const skewRef = useRef(0)

  const applyPayload = useCallback((data) => {
    setCfg(data.config || {})
    setStatus(data.status || {})
    setHelp(data.paramHelp || {})
    setGuide(data.guide || null)
    const st = data.status || {}
    const serverNow = Number(st.server_now) || Date.now() / 1000
    skewRef.current = serverNow - Date.now() / 1000
    if (st.next_at != null) {
      nextAtRef.current = Number(st.next_at)
      setRemain(Math.max(0, Number(st.next_at) - serverNow))
    } else {
      nextAtRef.current = null
      setRemain(null)
    }
  }, [])

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

  // Поллинг только статуса — локальные несохранённые правки cfg не затираем
  useEffect(() => {
    let cancelled = false
    const tick = async () => {
      if (document.visibilityState !== 'visible') return
      try {
        const data = await fetchSoftRestartOverview()
        if (cancelled) return
        const st = data.status || {}
        setStatus(st)
        const serverNow = Number(st.server_now) || Date.now() / 1000
        skewRef.current = serverNow - Date.now() / 1000
        if (st.next_at != null) {
          nextAtRef.current = Number(st.next_at)
          setRemain(Math.max(0, Number(st.next_at) - serverNow))
        } else {
          nextAtRef.current = null
          setRemain(null)
        }
      } catch {
        /* тихо */
      }
    }
    const id = setInterval(tick, 1500)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  // Живой отсчёт до секунды
  useEffect(() => {
    let raf = 0
    let last = 0
    const loop = (t) => {
      if (t - last > 200) {
        last = t
        const nextAt = nextAtRef.current
        if (nextAt == null) {
          setRemain(null)
        } else {
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
      if (res.status) {
        applyPayload({ config: res.config || cfg, status: res.status, paramHelp: help, guide })
      }
      notifyAdmin('Настройки Soft Restart сохранены')
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    } finally {
      setSaving(false)
    }
  }

  const onPreset = async (name) => {
    setSaving(true)
    try {
      const res = await saveSoftRestartPreset(name)
      if (res.config) setCfg(res.config)
      if (res.status) {
        applyPayload({ config: res.config || cfg, status: res.status, paramHelp: help, guide })
      }
      notifyAdmin(name === 'live' ? 'Пресет Live · авто ON' : 'Пресет Test · авто OFF')
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    } finally {
      setSaving(false)
    }
  }

  const onRestartNow = async () => {
    if (!window.confirm('Запустить soft restart сейчас? В личку придёт короткое «ок», когда новый процесс встанет.')) {
      return
    }
    setSaving(true)
    try {
      await queueSoftRestartNow('panel')
      notifyAdmin('Рестарт поставлен в очередь')
    } catch (e) {
      notifyAdmin(String(e?.message || e), { error: true })
    } finally {
      setSaving(false)
    }
  }

  const pulse = useMemo(() => {
    if (!status?.alive) return 'offline'
    if (status.requested) return 'restarting'
    if (cfg?.enabled) return 'armed'
    return 'idle'
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
          {guide?.subtitle || 'Мягкий перезапуск процесса без деплоя. Настройка здесь — в личку только короткое подтверждение.'}
        </p>

        <div className={`sr-countdown sr-countdown-${pulse}`}>
          <div className="sr-countdown-ring" aria-hidden="true">
            <span className="sr-countdown-glow" />
          </div>
          <div className="sr-countdown-body">
            <span className="sr-countdown-label">
              {!status?.alive
                ? 'бот не в сети'
                : !autoOn
                  ? 'авто выключен'
                  : status.requested
                    ? 'идёт рестарт…'
                    : remain == null
                      ? 'ещё не в расписании'
                      : 'до следующего рестарта'}
            </span>
            <span className="sr-countdown-clock" key={countdownActive ? Math.floor(remain) : 'x'}>
              {countdownActive ? fmtClock(remain) : '——:——'}
            </span>
            <span className="sr-countdown-meta">
              {countdownActive ? fmtHuman(remain) : status?.alive ? 'ожидание команды' : 'нет heartbeat'}
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
              label="Авто-рестарт"
              sub={help.enabled}
              onToggle={() => patch('enabled', !cfg.enabled)}
            />
            <Toggle
              on={!!cfg.test}
              label="Тестовый режим"
              sub={help.test}
              onToggle={() => patch('test', !cfg.test)}
            />

            <div className="sr-presets">
              <button type="button" className="sr-btn sr-btn-live" disabled={saving} onClick={() => onPreset('live')}>
                Preset Live
              </button>
              <button type="button" className="sr-btn sr-btn-ghost" disabled={saving} onClick={() => onPreset('test')}>
                Preset Test
              </button>
              <button type="button" className="sr-btn sr-btn-danger" disabled={saving} onClick={onRestartNow}>
                Рестарт сейчас
              </button>
            </div>

            <div className="sr-actions">
              <button type="button" className="sr-btn sr-btn-primary" disabled={saving} onClick={onSave}>
                {saving ? 'Сохраняю…' : 'Сохранить'}
              </button>
              <button type="button" className="sr-btn sr-btn-ghost" disabled={saving} onClick={load}>
                Обновить
              </button>
            </div>

            <p className="sr-note">
              После сохранения бот подхватывает настройки за ~1 секунду. В личку при рестарте —
              одно короткое сообщение вида <code>◈ soft restart · … · ок</code>.
            </p>
          </div>
        )}

        {tab === 'timing' && (
          <div className="sr-grid">
            <SliderRow
              label="Пауза до первого рестарта"
              help={help.initial_delay_sec}
              value={cfg.initial_delay_sec}
              min={30}
              max={21600}
              step={30}
              onChange={(n) => patch('initial_delay_sec', n)}
            />
            <SliderRow
              label="Интервал между рестартами"
              help={help.interval_sec}
              value={cfg.interval_sec}
              min={60}
              max={21600}
              step={60}
              onChange={(n) => patch('interval_sec', n)}
            />
            <SliderRow
              label="Grace (жёсткий выход)"
              help={help.grace_sec}
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
            <p className="sr-note">
              Ползунки и кнопки ± двигают значения. Сохранение сразу пересобирает расписание —
              отсчёт сверху обновится.
            </p>
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
            <p className="sr-note">
              Команды в личке бота по-прежнему работают (<code>.r</code>, <code>sypherrestart</code>),
              но вся настройка удобнее здесь. Чужим эта вкладка не видна.
            </p>
          </div>
        )}
      </div>
    </article>
  )
}
