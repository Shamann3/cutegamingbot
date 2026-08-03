import { useEffect, useRef, useState } from 'react'
import EntranceFlora from './decor/EntranceFlora'
import '../styles/farmEntrance.css'

const SESSION_KEY = 'cute_farm_entrance_v6'
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

      <EntranceFlora />

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
