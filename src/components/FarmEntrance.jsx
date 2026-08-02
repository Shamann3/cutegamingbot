import { useEffect, useRef, useState } from 'react'
import '../styles/farmEntrance.css'

const SESSION_KEY = 'cute_farm_entrance_v3'
/** Полный цикл: появление → пауза «прочитать» → выход. */
const TOTAL_MS = 4000
const OUT_MS = 480

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

/**
 * Premium entrance seal для фермы (~4с).
 * Телефон / планшет / ПК: fixed + safe-area + clamp().
 * Один раз за сессию браузера/WebView.
 */
export default function FarmEntrance({ active = false, onDone }) {
  const [phase, setPhase] = useState('idle') // idle | play | out | done
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

    const reduce = typeof window !== 'undefined'
      && window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
    const total = reduce ? 1200 : TOTAL_MS
    const outAt = Math.max(400, total - OUT_MS)

    setPhase('play')
    const outTimer = window.setTimeout(() => {
      if (!cancelled) setPhase('out')
    }, outAt)
    const doneTimer = window.setTimeout(() => {
      if (!cancelled) finish({ skipped: false })
    }, total)

    return () => {
      cancelled = true
      window.clearTimeout(outTimer)
      window.clearTimeout(doneTimer)
    }
  }, [active])

  if (phase === 'idle' || phase === 'done') return null

  return (
    <div
      className={`farm-ent-root${phase === 'out' ? ' farm-ent-root--out' : ''}`}
      role="presentation"
      aria-hidden="true"
    >
      <div className="farm-ent-void" />
      <div className="farm-ent-aurora" />
      <div className="farm-ent-vignette" />
      <div className="farm-ent-grid" />
      <div className="farm-ent-dust" aria-hidden />

      <div className="farm-ent-stage">
        <div className="farm-ent-orbit" aria-hidden>
          <svg className="farm-ent-svg" viewBox="0 0 200 200" fill="none">
            <circle className="farm-ent-ring farm-ent-ring--a" cx="100" cy="100" r="92" />
            <circle className="farm-ent-ring farm-ent-ring--b" cx="100" cy="100" r="78" />
            <circle className="farm-ent-ring farm-ent-ring--c" cx="100" cy="100" r="58" />
          </svg>
          <div className="farm-ent-brackets">
            <span className="farm-ent-bracket farm-ent-bracket--tl" />
            <span className="farm-ent-bracket farm-ent-bracket--tr" />
            <span className="farm-ent-bracket farm-ent-bracket--bl" />
            <span className="farm-ent-bracket farm-ent-bracket--br" />
          </div>
        </div>

        <div className="farm-ent-mark">
          <div className="farm-ent-stamp" aria-hidden />
          <div className="farm-ent-crest">
            <img
              src="/assets/cute-crest.png?v=3"
              alt="Cute Farming"
              draggable={false}
              className="farm-ent-crest-img"
            />
          </div>
        </div>

        <div className="farm-ent-copy">
          <p className="farm-ent-brand">CUTE FARMING</p>
          <p className="farm-ent-title">Ферма</p>
          <p className="farm-ent-line" aria-hidden />
          <p className="farm-ent-tag">выращивай · торгуй · побеждай</p>
        </div>
      </div>
    </div>
  )
}
