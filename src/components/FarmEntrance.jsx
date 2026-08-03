import { useEffect, useRef, useState } from 'react'
import { ensureTelegramFullscreen } from '../lib/telegram'
import '../styles/farmEntrance.css'

const SESSION_KEY = 'cute_farm_entrance_v9'
const CREST_SRC = '/assets/cute-crest-2x.png?v=7'
/** Как админская печать: ~6.0с ритуал + выход. */
export const FARM_ENTRANCE_HOLD_MS = 5550
export const FARM_ENTRANCE_EXIT_MS = 450
const LITE_HOLD_MS = 1600

export function hasSeenFarmEntrance() {
  try {
    return sessionStorage.getItem(SESSION_KEY) === '1'
  } catch {
    return false
  }
}

function markEntranceSeen() {
  try {
    sessionStorage.setItem(SESSION_KEY, '1')
  } catch {
    // WebView без storage
  }
}

function detectLite() {
  if (typeof window === 'undefined') return false
  try {
    if (localStorage.getItem('cf_farm_perf') === '1') return true
  } catch {
    /* ignore */
  }
  const prefersReduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  const weakCpu = (navigator.hardwareConcurrency || 4) <= 2
  return prefersReduced || weakCpu
}

/**
 * Полноэкранная печать входа — как admin EntranceSeal / SplashPage:
 * единственный экран, затем оболочка приложения.
 */
export default function FarmEntrance({ onDone }) {
  const [phase, setPhase] = useState('play') // play | out
  const [lite] = useState(detectLite)
  const doneRef = useRef(false)
  const onDoneRef = useRef(onDone)
  onDoneRef.current = onDone

  useEffect(() => {
    const finish = () => {
      if (doneRef.current) return
      doneRef.current = true
      document.documentElement.classList.remove('cute-entrance-playing')
      markEntranceSeen()
      onDoneRef.current?.({ skipped: false })
    }

    if (hasSeenFarmEntrance()) {
      finish()
      return undefined
    }

    ensureTelegramFullscreen()
    document.documentElement.classList.add('cute-entrance-playing')

    const warm = new Image()
    warm.src = CREST_SRC
    if (warm.decode) warm.decode().catch(() => {})

    const reduce = typeof window !== 'undefined'
      && window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
    const hold = reduce ? 700 : (lite ? LITE_HOLD_MS : FARM_ENTRANCE_HOLD_MS)
    const out = reduce ? 200 : FARM_ENTRANCE_EXIT_MS

    const outTimer = window.setTimeout(() => setPhase('out'), hold)
    const doneTimer = window.setTimeout(finish, hold + out)

    return () => {
      document.documentElement.classList.remove('cute-entrance-playing')
      window.clearTimeout(outTimer)
      window.clearTimeout(doneTimer)
    }
  }, [lite])

  return (
    <div
      className={`farm-ent-root${lite ? ' farm-ent-root--lite' : ''}${phase === 'out' ? ' farm-ent-root--out' : ''}`}
      role="status"
      aria-live="polite"
      aria-label="Вход на ферму Cute Farming"
    >
      <div className="farm-ent-void" aria-hidden />
      <div className="farm-ent-vignette" aria-hidden />
      <div className="farm-ent-grid" aria-hidden />
      <div className="farm-ent-aurora" aria-hidden />

      <div className="farm-ent-stage">
        <svg className="farm-ent-rings" viewBox="0 0 200 200" aria-hidden>
          <circle className="farm-ent-ring farm-ent-ring--a" cx="100" cy="100" r="94" />
          <circle className="farm-ent-ring farm-ent-ring--b" cx="100" cy="100" r="80" />
          <path
            className="farm-ent-ring farm-ent-ring--shield"
            d="M100 18 L162 40 V96 C162 136 134 164 100 178 C66 164 38 136 38 96 V40 Z"
          />
          <circle className="farm-ent-ring farm-ent-ring--c" cx="100" cy="100" r="56" />
        </svg>

        <div className="farm-ent-brackets" aria-hidden>
          <span className="farm-ent-bracket farm-ent-bracket--tl" />
          <span className="farm-ent-bracket farm-ent-bracket--tr" />
          <span className="farm-ent-bracket farm-ent-bracket--bl" />
          <span className="farm-ent-bracket farm-ent-bracket--br" />
        </div>

        <div className="farm-ent-mark">
          <div className="farm-ent-stamp" aria-hidden />
          <div className="farm-ent-crest">
            <img
              src={CREST_SRC}
              alt=""
              draggable={false}
              decoding="async"
              className="farm-ent-crest-img"
            />
          </div>
        </div>

        <div className="farm-ent-copy">
          <p className="farm-ent-kicker">Cute Farming</p>
          <p className="farm-ent-title">Ферма</p>
          <p className="farm-ent-sub">выращивай · торгуй · побеждай</p>
          <div className="farm-ent-rule" aria-hidden />
          <div className="farm-ent-meta" aria-hidden>
            <span>Грядки</span>
            <span className="farm-ent-meta-dot" />
            <span>Торговля</span>
            <span className="farm-ent-meta-dot" />
            <span>Крафт</span>
            <span className="farm-ent-meta-dot" />
            <span>Сезон</span>
          </div>
        </div>
      </div>

      <div className="farm-ent-flash" aria-hidden />
    </div>
  )
}
