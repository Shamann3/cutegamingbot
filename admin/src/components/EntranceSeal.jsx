import { useEffect, useRef, useState } from 'react'
import { hasTelegramInitData, isAdminSessionValid } from '../lib/adminClient'
import { vivoEpsilonLogo } from './EpsilonLogo'

/** Полный цикл печати: ~1.85s, выход ~0.35s */
export const ENTRANCE_HOLD_MS = 1850
export const ENTRANCE_EXIT_MS = 380
/** Укороченный цикл после логина */
export const ENTRANCE_LOGIN_HOLD_MS = 1550
/** Лёгкий режим (слабые устройства) */
export const ENTRANCE_LITE_HOLD_MS = 700

const PIECES = [
  { id: 'eye', label: 'Око' },
  { id: 'wing-l', label: 'Крыло' },
  { id: 'wing-r', label: 'Крыло' },
  { id: 'crown', label: 'Корона' },
  { id: 'wordmark', label: 'Марка' },
]

function detectLiteEntrance() {
  if (typeof window === 'undefined') return false
  try {
    if (localStorage.getItem('cf_admin_perf') === '1') return true
  } catch { /* ignore */ }
  const prefersReduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  const veryWeakCpu = (navigator.hardwareConcurrency || 4) <= 2
  // Полная анимация CSS-only и короткая; lite — только reduce-motion,
  // сохранённый «Лёгкий режим» или совсем слабый CPU.
  return prefersReduced || veryWeakCpu
}

/**
 * Кинематографичная ч/б печать входа: кольца защиты → сборка эмблемы
 * по кускам → штамп → короткий выход. Только transform/opacity.
 */
export default function EntranceSeal({
  displayName = '',
  variant = 'boot', // 'boot' | 'login'
  onFinished,
}) {
  const [phase, setPhase] = useState('in') // in | out
  const [lite] = useState(detectLiteEntrance)
  const doneRef = useRef(false)
  const holdMs = lite
    ? ENTRANCE_LITE_HOLD_MS
    : variant === 'login'
      ? ENTRANCE_LOGIN_HOLD_MS
      : ENTRANCE_HOLD_MS

  useEffect(() => {
    // Декодируем марку заранее — сборка кусков не ждёт первого paint.
    const warm = new Image()
    warm.src = vivoEpsilonLogo
    if (warm.decode) warm.decode().catch(() => {})

    const reduced =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

    const hold = reduced ? 420 : holdMs
    const exit = reduced ? 160 : ENTRANCE_EXIT_MS

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

  const title = authed ? 'Власть закреплена' : 'Защищённый контур'
  const greeting = authed
    ? (displayName ? `Доступ подтверждён, ${displayName}` : 'Доступ подтверждён')
    : (displayName ? `Добро пожаловать, ${displayName}` : 'Добро пожаловать')

  return (
    <div
      className={`ent-root ent-root--${variant}${lite ? ' ent-root--lite' : ''}${phase === 'out' ? ' ent-root--out' : ''}`}
      role="status"
      aria-live="polite"
      aria-label={greeting}
    >
      <div className="ent-void" aria-hidden="true" />
      <div className="ent-vignette" aria-hidden="true" />
      <div className="ent-grid" aria-hidden="true" />

      <div className="ent-stage">
        {/* Кольца + щит защиты — stroke-dash через CSS */}
        <svg className="ent-rings" viewBox="0 0 200 200" aria-hidden="true">
          <circle className="ent-ring ent-ring--a" cx="100" cy="100" r="92" />
          <circle className="ent-ring ent-ring--b" cx="100" cy="100" r="78" />
          <path
            className="ent-ring ent-ring--shield"
            d="M100 22 L158 42 V95 C158 132 132 158 100 172 C68 158 42 132 42 95 V42 Z"
          />
          <circle className="ent-ring ent-ring--c" cx="100" cy="100" r="58" />
          <circle className="ent-ring ent-ring--core" cx="100" cy="100" r="3.5" />
        </svg>

        <div className="ent-brackets" aria-hidden="true">
          <span className="ent-bracket ent-bracket--tl" />
          <span className="ent-bracket ent-bracket--tr" />
          <span className="ent-bracket ent-bracket--bl" />
          <span className="ent-bracket ent-bracket--br" />
        </div>

        <div className="ent-beam" aria-hidden="true" />

        <div className="ent-mark" aria-hidden="true">
          {PIECES.map((piece) => (
            <div
              key={piece.id}
              className={`ent-piece ent-piece--${piece.id}`}
            >
              <img
                src={vivoEpsilonLogo}
                alt=""
                draggable={false}
                decoding="async"
              />
            </div>
          ))}
          <div className="ent-piece ent-piece--full">
            <img
              src={vivoEpsilonLogo}
              alt=""
              draggable={false}
              decoding="async"
            />
          </div>
          <div className="ent-stamp" />
        </div>

        <div className="ent-copy">
          <p className="ent-kicker">Cute Epsilon</p>
          <p className="ent-title">{title}</p>
          <p className="ent-sub">{greeting}</p>
          <div className="ent-meta" aria-hidden="true">
            <span>AUTHORITY</span>
            <span className="ent-meta-dot" />
            <span>PROTECTION</span>
            <span className="ent-meta-dot" />
            <span>PANEL</span>
          </div>
        </div>
      </div>

      <div className="ent-flash" aria-hidden="true" />
    </div>
  )
}
