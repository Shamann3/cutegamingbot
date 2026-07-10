import { useEffect, useMemo, useRef, useState } from 'react'
import {
  SPLASH_FADEOUT_MS,
  SPLASH_HOLD_MS,
  SPLASH_LETTER_MS,
  SPLASH_EXIT_STAGGER_MS,
  pickEntranceVariant,
  pickExitVariant,
} from '../constants/splash'

function buildSegments(prefix, name) {
  const prefixChars = prefix.split('').map((char, index) => ({
    char,
    accent: false,
    entrance: pickEntranceVariant(index, char),
    exit: pickExitVariant(index),
    key: `p-${index}-${char}`,
  }))
  const offset = prefixChars.length
  const nameChars = name.split('').map((char, index) => ({
    char,
    accent: true,
    entrance: pickEntranceVariant(offset + index, char),
    exit: pickExitVariant(offset + index),
    key: `n-${index}-${char}`,
  }))
  return [...prefixChars, ...nameChars]
}

export default function AnimatedWelcome({ prefix, name, onFinished }) {
  const segments = useMemo(() => buildSegments(prefix, name), [prefix, name])
  const [visibleCount, setVisibleCount] = useState(0)
  const [phase, setPhase] = useState('enter')
  const finishedRef = useRef(false)

  useEffect(() => {
    if (visibleCount >= segments.length) return undefined

    const timer = window.setTimeout(() => {
      setVisibleCount((count) => count + 1)
    }, SPLASH_LETTER_MS)

    return () => window.clearTimeout(timer)
  }, [visibleCount, segments.length])

  useEffect(() => {
    if (visibleCount < segments.length) return undefined

    const holdTimer = window.setTimeout(() => {
      setPhase('exit')
    }, SPLASH_HOLD_MS)

    return () => window.clearTimeout(holdTimer)
  }, [visibleCount, segments.length])

  useEffect(() => {
    if (phase !== 'exit') return undefined

    const staggerMs = visibleCount * SPLASH_EXIT_STAGGER_MS
    const totalMs = Math.max(SPLASH_FADEOUT_MS, staggerMs + 1400)

    const exitTimer = window.setTimeout(() => {
      if (finishedRef.current) return
      finishedRef.current = true
      onFinished()
    }, totalMs)

    return () => window.clearTimeout(exitTimer)
  }, [phase, onFinished, visibleCount])

  const visibleSegments = segments.slice(0, visibleCount)
  const isExiting = phase === 'exit'

  return (
    <p
      className={`splash-text ${isExiting ? 'splash-text-exiting' : 'splash-text-entering'}`}
      aria-live="polite"
    >
      {visibleSegments.map((segment, index) => (
        <span
          key={segment.key}
          className={[
            'splash-char',
            segment.accent ? 'splash-char-accent' : '',
            isExiting ? segment.exit : segment.entrance,
          ]
            .filter(Boolean)
            .join(' ')}
          style={{ animationDelay: isExiting ? `${index * SPLASH_EXIT_STAGGER_MS}ms` : '0ms' }}
        >
          {segment.char === ' ' ? '\u00a0' : segment.char}
        </span>
      ))}
    </p>
  )
}
