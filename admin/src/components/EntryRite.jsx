import { useEffect, useMemo, useRef, useState } from 'react'

export const RITE_FIELD_MS = 760
export const RITE_GATHER_MS = 980
export const RITE_BURST_MS = 540
export const RITE_TAIL_MS = 90
export const RITE_STILL_MS = 400

const FULL = { cols: 8, rows: 12 }
const LITE = { cols: 6, rows: 8 }

function riteClock() {
  const still = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
  const lite = document.body.classList.contains('perf-light')
    || (navigator.hardwareConcurrency || 4) <= 2
  if (still) return { still: true, field: 0, gather: 0, burst: 0, tail: RITE_STILL_MS, ...LITE }
  if (lite) return { still: false, field: 420, gather: 520, burst: 320, tail: 60, ...LITE }
  return {
    still: false,
    field: RITE_FIELD_MS,
    gather: RITE_GATHER_MS,
    burst: RITE_BURST_MS,
    tail: RITE_TAIL_MS,
    ...FULL,
  }
}

function fieldCells(digits, cols, rows) {
  const marks = String(digits || '').replace(/\D/g, '').slice(0, 6).padEnd(6, '0').split('')
  const total = cols * rows
  const used = new Set()
  const slots = [0.11, 0.26, 0.4, 0.57, 0.72, 0.88].map((place) => {
    let index = Math.min(total - 1, Math.round(place * (total - 1)))
    while (used.has(index)) index = (index + 1) % total
    used.add(index)
    return index
  })
  return Array.from({ length: total }, (_, index) => {
    const slot = slots.indexOf(index)
    return {
      index,
      slot,
      digit: slot >= 0 ? marks[slot] : String((index * 7 + 3) % 10),
      col: index % cols,
      row: Math.floor(index / cols),
    }
  })
}

/**
 * Весь экран в числах. Шесть цифр кода вытягиваются в центр,
 * шифр вспыхивает с тряской, и только потом открывается загрузка панели.
 */
export default function EntryRite({ digits = '', onDone }) {
  const doneRef = useRef(onDone)
  doneRef.current = onDone
  const clock = useMemo(() => riteClock(), [])
  const cells = useMemo(
    () => fieldCells(digits, clock.cols, clock.rows),
    [digits, clock.cols, clock.rows],
  )
  const marks = String(digits || '').replace(/\D/g, '').slice(0, 6).split('')
  const [phase, setPhase] = useState(clock.still ? 'still' : 'field')

  useEffect(() => {
    if (clock.still) {
      const timer = window.setTimeout(() => doneRef.current?.(), clock.tail)
      return () => window.clearTimeout(timer)
    }
    const gatherAt = clock.field
    const burstAt = gatherAt + clock.gather
    const timers = [
      window.setTimeout(() => setPhase('gather'), gatherAt),
      window.setTimeout(() => setPhase('burst'), burstAt),
      window.setTimeout(() => doneRef.current?.(), burstAt + clock.burst + clock.tail),
    ]
    return () => timers.forEach((timer) => window.clearTimeout(timer))
  }, [clock])

  const note = phase === 'burst' || phase === 'still' ? 'Открываем загрузку' : 'Собираем ваш код'

  return (
    <div
      className={`rite is-${phase}`}
      style={{ '--cols': clock.cols, '--rows': clock.rows, '--pull': `${clock.gather}ms`, '--burst': `${clock.burst}ms` }}
      role="status"
      aria-live="polite"
      aria-label={note}
    >
      <p className="rite-sr">{note}</p>
      <div className="rite-world" aria-hidden="true">
        <div className="rite-field">
          {cells.map((cell) => (
            <span
              key={cell.index}
              className={`rite-cell${cell.slot >= 0 ? ' is-key' : ''}`}
              style={{ '--col': cell.col, '--row': cell.row, '--n': cell.index % 16, '--slot': Math.max(cell.slot, 0) }}
            >
              {cell.digit}
            </span>
          ))}
        </div>
        <span className="rite-ring" />
        <span className="rite-flash" />
      </div>
      {phase === 'still' && (
        <p className="rite-lock" aria-hidden="true">{marks.join('')}</p>
      )}
      <p className="rite-note" aria-hidden="true">{note}</p>
    </div>
  )
}
