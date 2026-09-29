import { useEffect, useMemo, useRef, useState } from 'react'
import { hasTelegramInitData, isAdminSessionValid } from '../lib/adminClient'
import { vivoEpsilonLogo } from './EpsilonLogo'
import { applyAccentToDocument, loadStoredAccent } from '../lib/accentTheme'
import MatrixRain from './MatrixRain'
import { waitForDashboardStats } from '../lib/dashboardPrefetch'

/**
 * Жёсткий таймлайн на 6.0с:
 *   0.00–1.10  сцена (фон / кольца)
 *   1.10–2.60  появление полного логотипа (1.5с)
 *   2.60–3.10  пауза 0.5с на «цельную» марку
 *   3.10–3.70  появление текста
 *   3.70–5.55  время прочитать
 *   5.55–6.00  выход → панель / auth
 */
export const ENTRANCE_HOLD_MS = 5550
export const ENTRANCE_EXIT_MS = 450
export const ENTRANCE_LOGIN_HOLD_MS = 5550
export const ENTRANCE_LITE_HOLD_MS = 1600
/** Сколько после таймлайна вход ещё ждёт статистику главной. */
export const ENTRANCE_DATA_GRACE_MS = 3000

function detectLiteEntrance() {
  if (typeof window === 'undefined') return false
  try {
    if (localStorage.getItem('cf_admin_perf') === '1') return true
  } catch { /* ignore */ }
  const prefersReduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  const veryWeakCpu = (navigator.hardwareConcurrency || 4) <= 2
  return prefersReduced || veryWeakCpu
}

/** Цвет заливки марки = bright из текущей палитры (форма PNG не трогаем). */
function resolveEntranceLogoTint() {
  if (typeof document === 'undefined') return '#9ecbb4'
  applyAccentToDocument(loadStoredAccent())
  const root = document.documentElement
  const bright = getComputedStyle(root).getPropertyValue('--e-accent-bright').trim()
  const base = getComputedStyle(root).getPropertyValue('--e-accent').trim()
  return bright || base || '#9ecbb4'
}

const TRACE_LINES = [
  '$ epsilon --boot --secure',
  '> палитра проекта ......... ok',
  '> сессия сотрудника ....... ok',
  '> вызовы бота ............. sync',
  '> сообщения групп ......... sync',
  '> оборот кут в играх ...... sync',
  '> realtime 1 Hz ........... ready',
]

const DATA_TRACE = {
  loading: '> статистика главной ..... загрузка',
  ready: '> статистика главной ..... ready',
  later: '> статистика главной ..... фон',
}

/**
 * Построчная «печать кода» — заполняет время визуальной загрузки.
 * tail — живая строка после скрипта (реальное состояние загрузки данных).
 */
function ConsoleTrace({ durationMs, tail = null }) {
  const script = useMemo(() => TRACE_LINES.join('\n'), [])
  const [typed, setTyped] = useState(0)

  useEffect(() => {
    const total = script.length
    // Печать занимает ~80% таймлайна, чтобы живая строка успела показаться.
    const step = Math.max(10, Math.floor((durationMs * 0.8) / Math.max(total, 1)))
    let i = 0
    const timer = window.setInterval(() => {
      i += 1
      setTyped(i)
      if (i >= total) window.clearInterval(timer)
    }, step)
    return () => window.clearInterval(timer)
  }, [script, durationMs])

  const done = typed >= script.length
  const visible = script.slice(0, typed).split('\n')
  if (done && tail) visible.push(tail)

  return (
    <pre className="ent-trace" aria-hidden="true">
      {visible.map((line, index) => (
        <span
          className={`ent-trace-line${done && tail && index === visible.length - 1 ? ' is-live' : ''}`}
          key={TRACE_LINES[index] || `tail-${index}`}
        >
          {line}
          {index === visible.length - 1 ? <i className="ent-trace-caret" /> : null}
        </span>
      ))}
    </pre>
  )
}

/**
 * Печать входа (ровно 6с).
 * Только оригинальный полный логотип — без SVG-дорисовок.
 */
export default function EntranceSeal({
  displayName = '',
  variant = 'boot',
  onFinished,
}) {
  const [phase, setPhase] = useState('in')
  const [lite] = useState(detectLiteEntrance)
  const [logoTint] = useState(resolveEntranceLogoTint)
  // После логина сразу открывается главная — её цифры грузим, пока идёт заставка.
  const needsData = variant === 'login'
  const [dataState, setDataState] = useState(needsData ? 'loading' : null)
  const doneRef = useRef(false)
  const holdMs = lite
    ? ENTRANCE_LITE_HOLD_MS
    : variant === 'login'
      ? ENTRANCE_LOGIN_HOLD_MS
      : ENTRANCE_HOLD_MS

  useEffect(() => {
    applyAccentToDocument(loadStoredAccent())
  }, [])

  useEffect(() => {
    if (!needsData) return undefined
    let alive = true
    waitForDashboardStats().then((snapshot) => {
      if (alive) setDataState(snapshot ? 'ready' : 'later')
    })
    return () => {
      alive = false
    }
  }, [needsData])

  const finish = () => {
    if (doneRef.current) return
    doneRef.current = true
    onFinished?.()
  }

  useEffect(() => {
    if (typeof Audio !== 'function') return undefined
    const audio = new Audio(`${import.meta.env.BASE_URL}track.wav`)
    audio.preload = 'auto'
    audio.loop = false
    let level = 0.7
    try {
      const stored = localStorage.getItem('cf_admin_music_volume')
      if (stored !== null) level = Math.max(0, Math.min(1, Number(stored)))
    } catch { /* ignore */ }
    audio.volume = level > 0 ? level * level : 0.49
    const played = audio.play()
    if (played && typeof played.catch === 'function') played.catch(() => {})
    return () => {
      audio.pause()
      audio.removeAttribute('src')
      audio.load()
    }
  }, [])

  useEffect(() => {
    const warm = new Image()
    warm.src = vivoEpsilonLogo
    if (warm.decode) warm.decode().catch(() => {})

    const reduced =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

    const hold = reduced ? 700 : holdMs
    const exit = reduced ? 200 : ENTRANCE_EXIT_MS
    const grace = needsData ? ENTRANCE_DATA_GRACE_MS : 0

    let alive = true
    const timers = []
    const later = (fn, ms) => timers.push(window.setTimeout(fn, ms))
    const leave = () => {
      if (!alive) return
      setPhase('out')
      later(finish, exit)
    }

    later(() => {
      if (!needsData) {
        leave()
        return
      }
      waitForDashboardStats(grace).then(leave)
    }, hold)
    later(finish, hold + grace + exit + 4000)

    return () => {
      alive = false
      timers.forEach((id) => window.clearTimeout(id))
    }
  }, [holdMs, needsData, onFinished])

  const authed =
    variant === 'login' || isAdminSessionValid() || hasTelegramInitData()

  const title = authed ? 'Панель управления' : 'Вход в панель'
  const greeting = authed
    ? (displayName
      ? `${displayName} · игроки, экономика, контент и поддержка`
      : 'Игроки, экономика, контент и поддержка — в одном месте')
    : (displayName
      ? `${displayName} · управление проектом в одном месте`
      : 'Управление проектом: игроки, экономика, контент')

  return (
    <div
      className={`ent-root ent-root--${variant}${lite ? ' ent-root--lite' : ''}${phase === 'out' ? ' ent-root--out' : ''}`}
      role="status"
      aria-live="polite"
      aria-label={greeting}
    >
      <div className="ent-void" aria-hidden="true" />
      <MatrixRain paused={lite} />
      <div className="ent-vignette" aria-hidden="true" />
      <div className="ent-grid" aria-hidden="true" />

      <div className="ent-stage">
        <div className="ent-crest">
          <svg className="ent-rings" viewBox="0 0 200 200" aria-hidden="true">
            <circle className="ent-ring ent-ring--a" cx="100" cy="100" r="92" />
            <circle className="ent-ring ent-ring--b" cx="100" cy="100" r="78" />
            <circle className="ent-ring ent-ring--c" cx="100" cy="100" r="64" />
          </svg>

          <div className="ent-brackets" aria-hidden="true">
            <span className="ent-bracket ent-bracket--tl" />
            <span className="ent-bracket ent-bracket--tr" />
            <span className="ent-bracket ent-bracket--bl" />
            <span className="ent-bracket ent-bracket--br" />
          </div>

          <div className="ent-mark" aria-hidden="true">
            {/*
              Оригинальный белый VivoEpsilon: luminance → заливка цвета палитры.
              Крылья, корона, глаз, текст — те же; меняется только цвет.
            */}
            <svg className="ent-logo-defs" width="0" height="0" aria-hidden="true" focusable="false">
              <defs>
                <filter id="entLogoTint" x="0" y="0" width="100%" height="100%" colorInterpolationFilters="sRGB">
                  <feColorMatrix in="SourceGraphic" type="luminanceToAlpha" result="alpha" />
                  <feFlood floodColor={logoTint} result="fill" />
                  <feComposite in="fill" in2="alpha" operator="in" />
                </filter>
              </defs>
            </svg>
            <div className="ent-logo">
              <img
                src={vivoEpsilonLogo}
                alt=""
                draggable={false}
                decoding="async"
              />
            </div>
            <div className="ent-stamp" />
          </div>
        </div>

        <div className="ent-copy">
          <p className="ent-title">{title}</p>
          <p className="ent-sub">{greeting}</p>
          <div className="ent-rule" aria-hidden="true" />
          <div className="ent-meta" aria-hidden="true">
            <span>Игроки</span>
            <span className="ent-meta-dot" />
            <span>Экономика</span>
            <span className="ent-meta-dot" />
            <span>Контент</span>
            <span className="ent-meta-dot" />
            <span>Поддержка</span>
          </div>
          {!lite && (
            <ConsoleTrace
              durationMs={holdMs}
              tail={dataState ? DATA_TRACE[dataState] : null}
            />
          )}
        </div>
      </div>

      <div className="ent-flash" aria-hidden="true" />
    </div>
  )
}
