import { useEffect, useRef, useState } from 'react'
import { hasTelegramInitData, isAdminSessionValid } from '../lib/adminClient'
import { vivoEpsilonLogo } from './EpsilonLogo'

/** ~6.5s hold + ~0.5s exit ≈ 7 секунд */
export const ENTRANCE_HOLD_MS = 6500
export const ENTRANCE_EXIT_MS = 500
export const ENTRANCE_LOGIN_HOLD_MS = 6500
export const ENTRANCE_LITE_HOLD_MS = 1600

/** Куски герба — как в первой версии, но с чистым финальным штампом */
const PIECES = [
  { id: 'eye' },
  { id: 'wing-l' },
  { id: 'wing-r' },
  { id: 'crown' },
  { id: 'wordmark' },
]

function detectLiteEntrance() {
  if (typeof window === 'undefined') return false
  try {
    if (localStorage.getItem('cf_admin_perf') === '1') return true
  } catch { /* ignore */ }
  const prefersReduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  const veryWeakCpu = (navigator.hardwareConcurrency || 4) <= 2
  return prefersReduced || veryWeakCpu
}

/**
 * Heraldic Assembly — элитная печать входа (~7с).
 * Сборка кусков → единый штамп полного логотипа (без дублей текста) → копирайт.
 * Показывается и при первом заходе (до регистрации/логина), и после входа.
 */
export default function EntranceSeal({
  displayName = '',
  variant = 'boot', // boot | login
  onFinished,
}) {
  const [phase, setPhase] = useState('in')
  const [lite] = useState(detectLiteEntrance)
  const doneRef = useRef(false)

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

    const hold = reduced ? 550 : holdMs
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

  // boot до авторизации — «порог»; login / уже в сессии — «власть»
  const authed =
    variant === 'login' || isAdminSessionValid() || hasTelegramInitData()

  const title = authed ? 'Власть системы' : 'Порог системы'
  const greeting = authed
    ? (displayName ? `${displayName} · контроль открыт` : 'Контроль открыт')
    : (displayName ? `${displayName} · вход разрешён` : 'Вход в закрытый контур')

  return (
    <div
      className={`ent-root ent-root--herald ent-root--${variant}${lite ? ' ent-root--lite' : ''}${phase === 'out' ? ' ent-root--out' : ''}`}
      role="status"
      aria-live="polite"
      aria-label={greeting}
    >
      <div className="ent-void" aria-hidden="true" />
      <div className="ent-vignette" aria-hidden="true" />
      <div className="ent-grid" aria-hidden="true" />
      <div className="ent-sheen-bg" aria-hidden="true" />

      <div className="ent-stage">
        <svg className="ent-rings" viewBox="0 0 200 200" aria-hidden="true">
          <circle className="ent-ring ent-ring--a" cx="100" cy="100" r="96" />
          <circle className="ent-ring ent-ring--b" cx="100" cy="100" r="82" />
          <path
            className="ent-ring ent-ring--shield"
            d="M100 16 L164 38 V98 C164 138 136 166 100 180 C64 166 36 138 36 98 V38 Z"
          />
          <circle className="ent-ring ent-ring--c" cx="100" cy="100" r="58" />
          <circle className="ent-ring ent-ring--core" cx="100" cy="100" r="3" />
        </svg>

        <div className="ent-brackets" aria-hidden="true">
          <span className="ent-bracket ent-bracket--tl" />
          <span className="ent-bracket ent-bracket--tr" />
          <span className="ent-bracket ent-bracket--bl" />
          <span className="ent-bracket ent-bracket--br" />
        </div>

        <div className="ent-beam ent-beam--a" aria-hidden="true" />
        <div className="ent-beam ent-beam--b" aria-hidden="true" />

        <div className="ent-mark" aria-hidden="true">
          {/* Куски — собираются по очереди; на штампе гасятся */}
          {PIECES.map((piece) => (
            <div key={piece.id} className={`ent-piece ent-piece--${piece.id}`}>
              <img src={vivoEpsilonLogo} alt="" draggable={false} decoding="async" />
            </div>
          ))}

          {/* Единственный финальный логотип (PNG уже с CUTE EPSILON) */}
          <div className="ent-piece ent-piece--full">
            <img src={vivoEpsilonLogo} alt="" draggable={false} decoding="async" />
          </div>

          <div className="ent-stamp" />
          <div className="ent-mark-glow" />
          <div className="ent-logo-sheen" />
        </div>

        <div className="ent-copy">
          <p className="ent-kicker">Command access</p>
          <p className="ent-title">{title}</p>
          <p className="ent-sub">{greeting}</p>
          <p className="ent-line">
            Закрытый контур управления. Серьёзный проект — без права на ошибку.
          </p>
          <div className="ent-rule" aria-hidden="true" />
          <div className="ent-meta" aria-hidden="true">
            <span>AUTHORITY</span>
            <span className="ent-meta-dot" />
            <span>PROTECTION</span>
            <span className="ent-meta-dot" />
            <span>CONTROL</span>
          </div>
        </div>
      </div>

      <div className="ent-flash" aria-hidden="true" />
    </div>
  )
}
