import { useEffect, useMemo, useRef, useState } from 'react'
import { hasTelegramInitData, isAdminSessionValid } from '../lib/adminClient'
import { vivoEpsilonLogo } from './EpsilonLogo'

/** ~5.5s hold + ~0.5s exit ≈ 6s — Iris Awakening */
export const ENTRANCE_HOLD_MS = 5500
export const ENTRANCE_EXIT_MS = 500
export const ENTRANCE_LOGIN_HOLD_MS = 5300
export const ENTRANCE_LITE_HOLD_MS = 1400

/** 10 тонких лучей — достаточно для гипноза, без фейерверка */
const RAY_COUNT = 10

function detectLiteEntrance() {
  if (typeof window === 'undefined') return false
  try {
    if (localStorage.getItem('cf_admin_perf') === '1') return true
  } catch { /* ignore */ }
  const prefersReduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  const veryWeakCpu = (navigator.hardwareConcurrency || 4) <= 2
  return prefersReduced || veryWeakCpu
}

function buildRays(count) {
  const cx = 100
  const cy = 88 // центр ока в viewBox колец
  const inner = 10
  const outer = 72
  return Array.from({ length: count }, (_, i) => {
    const deg = (360 / count) * i - 90
    const rad = (deg * Math.PI) / 180
    return {
      x1: cx + Math.cos(rad) * inner,
      y1: cy + Math.sin(rad) * inner,
      x2: cx + Math.cos(rad) * outer,
      y2: cy + Math.sin(rad) * outer,
    }
  })
}

/**
 * Iris Awakening — око раскрывается, лучи, затем герб, wordmark, текст.
 * Слои сменяют друг друга по времени (без каши из overlapping clip’ов).
 */
export default function EntranceSeal({
  displayName = '',
  variant = 'boot',
  onFinished,
}) {
  const [phase, setPhase] = useState('in')
  const [lite] = useState(detectLiteEntrance)
  const doneRef = useRef(false)
  const rays = useMemo(() => buildRays(RAY_COUNT), [])

  const holdMs = lite
    ? ENTRANCE_LITE_HOLD_MS
    : variant === 'login'
      ? ENTRANCE_LOGIN_HOLD_MS
      : ENTRANCE_HOLD_MS

  useEffect(() => {
    const warm = new Image()
    warm.src = vivoEpsilonLogo
    if (warm.decode) warm.decode().catch(() => {})

    const reduced =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

    const hold = reduced ? 500 : holdMs
    const exit = reduced ? 180 : ENTRANCE_EXIT_MS

    const t1 = window.setTimeout(() => setPhase('out'), hold)
    const t2 = window.setTimeout(() => {
      if (doneRef.current) return
      doneRef.current = true
      onFinished?.()
    }, hold + exit)

    return () => {
      window.clearTimeout(t1)
      window.clearTimeout(t2)
    }
  }, [holdMs, onFinished])

  const authed =
    variant === 'login' || isAdminSessionValid() || hasTelegramInitData()

  const title = authed ? 'Власть системы' : 'Серьёзный контур'
  const greeting = authed
    ? (displayName
      ? `${displayName} · полный контроль`
      : 'Полный контроль открыт')
    : (displayName
      ? `${displayName} · вход в систему`
      : 'Вход в закрытую систему')

  return (
    <div
      className={`ent-root ent-root--iris ent-root--${variant}${lite ? ' ent-root--lite' : ''}${phase === 'out' ? ' ent-root--out' : ''}`}
      role="status"
      aria-live="polite"
      aria-label={greeting}
    >
      <div className="ent-void" aria-hidden="true" />
      <div className="ent-vignette" aria-hidden="true" />
      <div className="ent-grid" aria-hidden="true" />

      <div className="ent-stage">
        <svg className="ent-rings" viewBox="0 0 200 200" aria-hidden="true">
          <circle className="ent-ring ent-ring--a" cx="100" cy="100" r="94" />
          <circle className="ent-ring ent-ring--b" cx="100" cy="100" r="78" />
          <circle className="ent-ring ent-ring--c" cx="100" cy="100" r="52" />
          <g className="ent-rays">
            {rays.map((ray, i) => (
              <line
                key={i}
                className="ent-ray"
                style={{ '--ray-i': i }}
                x1={ray.x1}
                y1={ray.y1}
                x2={ray.x2}
                y2={ray.y2}
              />
            ))}
          </g>
          <circle className="ent-ring ent-ring--core" cx="100" cy="88" r="2.8" />
        </svg>

        <div className="ent-mark" aria-hidden="true">
          <div className="ent-eye-bloom" />

          {/* 1. Око — круговая маска */}
          <div className="ent-layer ent-layer--eye">
            <img src={vivoEpsilonLogo} alt="" draggable={false} decoding="async" />
          </div>

          {/* 2. Герб (корона + крылья + око) — после ока */}
          <div className="ent-layer ent-layer--crest">
            <img src={vivoEpsilonLogo} alt="" draggable={false} decoding="async" />
          </div>

          {/* 3. Полный consolidate герба */}
          <div className="ent-layer ent-layer--full">
            <img src={vivoEpsilonLogo} alt="" draggable={false} decoding="async" />
          </div>

          <div className="ent-stamp" />

          {/* Wordmark отдельно — трекинг сжимается */}
          <div className="ent-wordmark">
            <span className="ent-wm-line ent-wm-line--cute">CUTE</span>
            <span className="ent-wm-line ent-wm-line--eps">EPSILON</span>
          </div>
        </div>

        <div className="ent-copy">
          <p className="ent-kicker">Cute Epsilon</p>
          <p className="ent-title">{title}</p>
          <p className="ent-sub">{greeting}</p>
          <p className="ent-line">
            Закрытый контур управления. Без права на ошибку.
          </p>
          <div className="ent-rule" aria-hidden="true" />
          <div className="ent-meta" aria-hidden="true">
            <span>POWER</span>
            <span className="ent-meta-dot" />
            <span>SYSTEM</span>
            <span className="ent-meta-dot" />
            <span>CONTROL</span>
          </div>
        </div>
      </div>

      <div className="ent-flash" aria-hidden="true" />
    </div>
  )
}
