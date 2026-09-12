import { useEffect, useRef, useState } from 'react'
import { hasTelegramInitData, isAdminSessionValid } from '../lib/adminClient'
import { vivoEpsilonLogo } from './EpsilonLogo'
import { applyAccentToDocument, loadStoredAccent } from '../lib/accentTheme'

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
    const warm = new Image()
    warm.src = vivoEpsilonLogo
    if (warm.decode) warm.decode().catch(() => {})

    const reduced =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

    const hold = reduced ? 700 : holdMs
    const exit = reduced ? 200 : ENTRANCE_EXIT_MS

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
        </div>
      </div>

      <div className="ent-flash" aria-hidden="true" />
    </div>
  )
}
