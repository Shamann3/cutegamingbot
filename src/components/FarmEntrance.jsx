import { useEffect, useRef, useState } from 'react'
import '../styles/farmEntrance.css'

const SESSION_KEY = 'cute_farm_entrance_v5'
const CREST_SRC = '/assets/cute-crest.png?v=4'
/** Как админская печать: ~6.0с ритуал + выход. */
const HOLD_MS = 5550
const OUT_MS = 450
const LITE_HOLD_MS = 1600

function hasSeenEntrance() {
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
 * Эпичная печать входа на ферму (black / gold / green).
 * Структура как у админского EntranceSeal: void → rings/shield → crest → copy → flash → out.
 */
export default function FarmEntrance({ active = false, onDone }) {
  const [phase, setPhase] = useState('idle') // idle | play | out | done
  const [lite] = useState(detectLite)
  const finishedRef = useRef(false)
  const playingRef = useRef(false)
  const onDoneRef = useRef(onDone)
  onDoneRef.current = onDone

  useEffect(() => {
    const finish = ({ skipped = false, persist = true } = {}) => {
      if (finishedRef.current) {
        onDoneRef.current?.({ skipped: true })
        return
      }
      finishedRef.current = true
      playingRef.current = false
      if (persist) markEntranceSeen()
      setPhase('done')
      onDoneRef.current?.({ skipped })
    }

    if (!active) {
      if (playingRef.current && !finishedRef.current) {
        finish({ skipped: true, persist: false })
      } else if (finishedRef.current) {
        onDoneRef.current?.({ skipped: true })
      }
      return undefined
    }

    if (finishedRef.current) {
      onDoneRef.current?.({ skipped: true })
      return undefined
    }

    if (hasSeenEntrance()) {
      finish({ skipped: true })
      return undefined
    }

    let cancelled = false
    playingRef.current = true

    const warm = new Image()
    warm.src = CREST_SRC
    if (warm.decode) warm.decode().catch(() => {})

    const reduce = typeof window !== 'undefined'
      && window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
    const hold = reduce ? 700 : (lite ? LITE_HOLD_MS : HOLD_MS)
    const out = reduce ? 200 : OUT_MS

    setPhase('play')
    const outTimer = window.setTimeout(() => {
      if (!cancelled) setPhase('out')
    }, hold)
    const doneTimer = window.setTimeout(() => {
      if (!cancelled) finish({ skipped: false })
    }, hold + out)

    return () => {
      cancelled = true
      window.clearTimeout(outTimer)
      window.clearTimeout(doneTimer)
    }
  }, [active, lite])

  if (phase === 'idle' || phase === 'done') return null

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

      {/* Доп. слой растительности — оплетает сцену, не заменяет печать */}
      <svg className="farm-ent-flora" viewBox="0 0 360 640" preserveAspectRatio="xMidYMid slice" aria-hidden>
        <g className="farm-ent-flora-branch farm-ent-flora-branch--l" fill="none" strokeLinecap="round">
          <path className="farm-ent-flora-stem" d="M8 520 C40 420, 28 300, 62 210 C88 145, 70 90, 96 40" />
          <path className="farm-ent-flora-stem farm-ent-flora-stem--soft" d="M22 540 C54 450, 48 340, 78 250" />
          <path className="farm-ent-flora-leaf" d="M54 250 C68 232, 88 236, 90 252 C76 258, 64 260, 54 250Z" />
          <path className="farm-ent-flora-leaf" d="M70 190 C86 168, 108 174, 108 192 C92 198, 80 200, 70 190Z" />
          <path className="farm-ent-flora-leaf" d="M82 130 C98 108, 120 116, 118 134 C102 138, 90 140, 82 130Z" />
          <path className="farm-ent-flora-leaf" d="M90 78 C104 58, 124 66, 122 84 C108 88, 96 88, 90 78Z" />
        </g>
        <g className="farm-ent-flora-branch farm-ent-flora-branch--r" fill="none" strokeLinecap="round">
          <path className="farm-ent-flora-stem" d="M352 520 C320 420, 332 300, 298 210 C272 145, 290 90, 264 40" />
          <path className="farm-ent-flora-stem farm-ent-flora-stem--soft" d="M338 540 C306 450, 312 340, 282 250" />
          <path className="farm-ent-flora-leaf" d="M306 250 C292 232, 272 236, 270 252 C284 258, 296 260, 306 250Z" />
          <path className="farm-ent-flora-leaf" d="M290 190 C274 168, 252 174, 252 192 C268 198, 280 200, 290 190Z" />
          <path className="farm-ent-flora-leaf" d="M278 130 C262 108, 240 116, 242 134 C258 138, 270 140, 278 130Z" />
          <path className="farm-ent-flora-leaf" d="M270 78 C256 58, 236 66, 238 84 C252 88, 264 88, 270 78Z" />
        </g>
        <g className="farm-ent-flora-ground" fill="none">
          <path className="farm-ent-flora-stem farm-ent-flora-stem--ground" d="M40 600 C120 575, 240 575, 320 600" />
          <path className="farm-ent-flora-blade" d="M70 598 C74 560, 66 540, 72 520" />
          <path className="farm-ent-flora-blade" d="M110 600 C118 555, 104 535, 112 510" />
          <path className="farm-ent-flora-blade" d="M180 602 C176 560, 186 540, 178 515" />
          <path className="farm-ent-flora-blade" d="M250 600 C258 555, 246 535, 254 512" />
          <path className="farm-ent-flora-blade" d="M300 598 C294 562, 304 542, 296 522" />
        </g>
        <g className="farm-ent-flora-spores">
          <circle className="farm-ent-flora-spore farm-ent-flora-spore--1" cx="90" cy="300" r="2.2" />
          <circle className="farm-ent-flora-spore farm-ent-flora-spore--2" cx="270" cy="260" r="1.8" />
          <circle className="farm-ent-flora-spore farm-ent-flora-spore--3" cx="140" cy="420" r="2" />
          <circle className="farm-ent-flora-spore farm-ent-flora-spore--4" cx="220" cy="380" r="1.6" />
        </g>
      </svg>

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
          <p className="farm-ent-kicker">CUTE FARMING</p>
          <p className="farm-ent-title">Ферма</p>
          <p className="farm-ent-sub">выращивай · торгуй · побеждай</p>
          <p className="farm-ent-rule" aria-hidden />
          <p className="farm-ent-meta">печать входа · сезон открыт</p>
        </div>
      </div>

      <div className="farm-ent-flash" aria-hidden />
    </div>
  )
}
