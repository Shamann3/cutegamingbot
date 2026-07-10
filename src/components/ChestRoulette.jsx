import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { buildStrip, buildIdleStrip, landingOffset } from '../utils/rouletteStrip'
import { RARITY_ACCENT } from '../constants/chests'

const CELL = 78
const GAP = 10

export default function ChestRoulette({ result, pool, spinning, onDone }) {
  const viewportRef = useRef(null)
  const [offset, setOffset] = useState(0)
  const [animating, setAnimating] = useState(false)
  const strip = result
    ? buildStrip(result, pool || [], { length: 40, resultIndex: 35 })
    : (pool && pool.length ? buildIdleStrip(pool) : null)

  useLayoutEffect(() => {
    if (!spinning || !result || !viewportRef.current) {
      // Not spinning (either never started, or interrupted mid-flight): make
      // sure we don't leave `animating` stuck true from a prior spin that
      // never reached its transitionend.
      setAnimating((prev) => (prev ? false : prev))
      return
    }
    let cancelled = false
    const vw = viewportRef.current.clientWidth
    // start from 0, then next frame animate to the landing offset
    setOffset(0)
    setAnimating(false)
    const rafIds = []
    rafIds[0] = requestAnimationFrame(() => {
      rafIds[1] = requestAnimationFrame(() => {
        if (cancelled) return
        setAnimating(true)
        setOffset(landingOffset(35, CELL, GAP, vw))
      })
    })
    return () => {
      cancelled = true
      rafIds.forEach((id) => id !== undefined && cancelAnimationFrame(id))
    }
  }, [spinning, result])

  const handleTransitionEnd = () => {
    if (animating) {
      setAnimating(false)
      onDone?.()
    }
  }

  if (!strip) {
    return <div className="chest-roulette chest-roulette-empty" ref={viewportRef} />
  }

  // Only drift idly when there's truly nothing landed to show: before the
  // first spin (offset still 0) or once fully reset. A landed strip (offset
  // non-zero) must stay put instead of snapping back to translateX(0).
  const isIdle = !spinning && !animating && offset === 0

  return (
    <div className="chest-roulette" ref={viewportRef}>
      <div className="chest-roulette-pointer" />
      <div
        className={`chest-roulette-strip${isIdle ? ' chest-roulette-idle' : ''}`}
        style={animating
          ? { transform: `translateX(${offset}px)`, transition: 'transform 3.4s cubic-bezier(.12,.72,.16,1)' }
          : { transform: `translateX(${offset}px)` }}
        onTransitionEnd={handleTransitionEnd}
      >
        {strip.cells.map((c) => (
          <div key={c.key} className="chest-cell" style={{ borderColor: RARITY_ACCENT[c.rarity] }}>
            <span>{c.emoji}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
