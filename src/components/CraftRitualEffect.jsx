import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react'
import { formatRecipeLine } from '../utils/craftMatch'
import {
  areOrbitsAligned,
  fuseAngles,
  fuseDurationMs,
  orbitAngles,
  orbitPeriodMs,
} from '../utils/craftRitualOrbit'

const TICK_COUNT = 16
const SPARKS = 10
const EMBER_COUNT = 10
const SHARD_COUNT = 14
const RING_FRAGMENTS = 8
const LITE_SPARKS = 5
const LITE_SHARDS = 8

function tierClass(performanceTier) {
  if (performanceTier === 'turbo') return 'craft-ritual-layer--turbo-tier'
  if (performanceTier === 'lite') return 'craft-ritual-layer--lite-tier'
  return 'craft-ritual-layer--full-tier'
}

function phaseReach(phase, target) {
  const order = ['invoke', 'orbit', 'fuse', 'sigil', 'success', 'fail']
  const current = order.indexOf(phase)
  const goal = order.indexOf(target)
  if (current < 0 || goal < 0) return false
  return current >= goal
}

function RitualCrumble({ slotA, slotB, variant = 'compact' }) {
  const shardCount = variant === 'showcase' || variant === 'backdrop' ? SHARD_COUNT : LITE_SHARDS
  const fragCount = variant === 'backdrop' ? RING_FRAGMENTS : 6

  return (
    <div className={`craft-ritual-crumble craft-ritual-crumble--${variant}`} aria-hidden>
      <span className="craft-ritual-crumble-ring" />
      {Array.from({ length: fragCount }, (_, index) => (
        <span
          key={`frag-${index}`}
          className="craft-ritual-ring-fragment"
          style={{ '--ritual-i': index, '--ritual-n': fragCount }}
        />
      ))}
      <div className="craft-ritual-crumble-core">
        <span className="craft-ritual-crumble-orb craft-ritual-crumble-orb--a">{slotA?.emoji ?? '·'}</span>
        <span className="craft-ritual-crumble-orb craft-ritual-crumble-orb--b">{slotB?.emoji ?? '·'}</span>
      </div>
      <span className="craft-ritual-crumble-crack" />
      {Array.from({ length: shardCount }, (_, index) => (
        <span
          key={`shard-${index}`}
          className="craft-ritual-shard"
          style={{ '--ritual-i': index, '--ritual-n': shardCount }}
        >
          <span className="craft-ritual-shard-bit">
            {index % 2 === 0 ? (slotA?.emoji ?? '·') : (slotB?.emoji ?? '·')}
          </span>
        </span>
      ))}
      <span className="craft-ritual-crumble-dust" />
    </div>
  )
}

function TurboRitual({ phase, slotA, slotB, result }) {
  const isBlend = phase === 'blend'
  const isSuccess = phase === 'success'
  const isFail = phase === 'fail'

  return (
    <div
      className={[
        'craft-ritual-layer',
        'craft-ritual-layer--flow',
        'craft-ritual-layer--turbo-tier',
        `craft-ritual-layer--${phase}`,
      ].join(' ')}
      aria-hidden
    >
      {isBlend ? (
        <div className="craft-ritual-turbo">
          <div className="craft-ritual-turbo-ring" aria-hidden />
          <div className="craft-ritual-turbo-row">
            <span className="craft-ritual-turbo-orb craft-ritual-turbo-orb--a">{slotA?.emoji ?? '·'}</span>
            <span className="craft-ritual-turbo-join" aria-hidden />
            <span className="craft-ritual-turbo-orb craft-ritual-turbo-orb--b">{slotB?.emoji ?? '·'}</span>
          </div>
        </div>
      ) : null}

      {isSuccess ? (
        <div
          className="craft-ritual-resolve craft-ritual-resolve--success"
          aria-label={result?.name ?? 'Готово'}
        >
          <span className="craft-ritual-resolve-emoji">{result?.emoji ?? '·'}</span>
        </div>
      ) : null}

      {isFail ? (
        <div className="craft-ritual-resolve craft-ritual-resolve--fail" aria-label="Не вышло">
          <RitualCrumble slotA={slotA} slotB={slotB} variant="compact" />
        </div>
      ) : null}
    </div>
  )
}

const CraftRitualEffect = forwardRef(function CraftRitualEffect({
  phase,
  slotA,
  slotB,
  result,
  recipe = null,
  performanceTier = 'full',
}, ref) {
  const periodMs = orbitPeriodMs(performanceTier)
  const fuseMs = fuseDurationMs(performanceTier)

  const [motion, setMotion] = useState({
    angleA: 0,
    angleB: 180,
    merge: 0,
    scale: 1,
    orbOpacity: 1,
    driven: false,
  })

  const phaseRef = useRef(phase)
  const orbitEpochRef = useRef(null)
  const fuseEpochRef = useRef(null)
  const fuseStartRef = useRef({ angleA: 0, angleB: 0 })
  const alignWaitRef = useRef(null)
  const fuseWaitRef = useRef(null)
  const lastAlignAtRef = useRef(0)
  const rafRef = useRef(0)

  phaseRef.current = phase

  const motionRef = useRef(motion)
  motionRef.current = motion

  useImperativeHandle(ref, () => ({
    waitAlignments(count, { minMs = 0, maxMs = 8000 } = {}) {
      return new Promise((resolve) => {
        orbitEpochRef.current = performance.now()
        lastAlignAtRef.current = 0
        setMotion({
          angleA: 0,
          angleB: 180,
          merge: 0,
          scale: 1,
          orbOpacity: 1,
          driven: true,
        })
        alignWaitRef.current = {
          need: count,
          seen: 0,
          minMs,
          maxMs,
          startedAt: performance.now(),
          resolve,
        }
      })
    },

    runFuse(durationMs = fuseMs, start = null) {
      return new Promise((resolve) => {
        fuseStartRef.current = start
          ? { angleA: start.angleA, angleB: start.angleB }
          : { angleA: motionRef.current.angleA, angleB: motionRef.current.angleB }
        fuseEpochRef.current = performance.now()
        fuseWaitRef.current = { durationMs, resolve }
      })
    },
  }), [fuseMs])

  useEffect(() => {
    if (phase === 'invoke') {
      orbitEpochRef.current = null
      fuseEpochRef.current = null
      alignWaitRef.current = null
      fuseWaitRef.current = null
      setMotion({
        angleA: 0,
        angleB: 180,
        merge: 0,
        scale: 1,
        orbOpacity: 1,
        driven: false,
      })
    }

    if (phase !== 'orbit' && phase !== 'fuse') {
      if (phase !== 'invoke') {
        orbitEpochRef.current = null
      }
      fuseEpochRef.current = null
    }
  }, [phase])

  useEffect(() => {
    const drivenPhases = ['orbit', 'fuse', 'invoke']
    if (!drivenPhases.includes(phase) && !alignWaitRef.current && !fuseWaitRef.current) {
      return undefined
    }

    const loop = (now) => {
      const currentPhase = phaseRef.current

      if (fuseWaitRef.current && fuseEpochRef.current !== null) {
        const fuseWait = fuseWaitRef.current
        const duration = fuseWait.durationMs ?? fuseMs
        const elapsed = now - fuseEpochRef.current
        const { angleA, angleB } = fuseStartRef.current
        const fused = fuseAngles(elapsed, duration, angleA, angleB)

        setMotion({
          angleA: fused.angleA,
          angleB: fused.angleB,
          merge: fused.merge,
          scale: fused.scale,
          orbOpacity: fused.orbOpacity,
          driven: true,
        })

        if (elapsed >= duration) {
          const done = fuseWait
          fuseWaitRef.current = null
          done.resolve({ ...fused, elapsed })
        }
      } else if (orbitEpochRef.current !== null) {
        const elapsed = now - orbitEpochRef.current
        const { angleA, angleB } = orbitAngles(elapsed, periodMs)

        setMotion({
          angleA,
          angleB,
          merge: 0,
          scale: 1,
          orbOpacity: 1,
          driven: true,
        })

        const alignWait = alignWaitRef.current
        if (alignWait && areOrbitsAligned(angleA, angleB)) {
          const halfPeriod = periodMs / 2
          if (now - lastAlignAtRef.current > halfPeriod * 0.35) {
            lastAlignAtRef.current = now
            alignWait.seen += 1

            const waited = now - alignWait.startedAt
            if (alignWait.seen >= alignWait.need && waited >= alignWait.minMs) {
              alignWaitRef.current = null
              alignWait.resolve({ angleA, angleB, elapsed, alignments: alignWait.seen })
            }
          }
        }

        if (alignWait && now - alignWait.startedAt >= alignWait.maxMs) {
          alignWaitRef.current = null
          alignWait.resolve({ angleA, angleB, elapsed, timeout: true })
        }
      }

      rafRef.current = requestAnimationFrame(loop)
    }

    rafRef.current = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(rafRef.current)
  }, [phase, periodMs, fuseMs])

  useEffect(() => () => cancelAnimationFrame(rafRef.current), [])

  if (!phase) return null

  if (performanceTier === 'turbo') {
    return (
      <TurboRitual
        phase={phase}
        slotA={slotA}
        slotB={slotB}
        result={result}
      />
    )
  }

  const isLite = performanceTier === 'lite'
  const isFull = performanceTier === 'full'
  const isSuccess = phase === 'success'
  const isFail = phase === 'fail'
  const isCasting = phaseReach(phase, 'invoke') && !isSuccess && !isFail
  const showCircle = isCasting || isSuccess || isFail
  const showTicks = isFull && phaseReach(phase, 'invoke') && !isSuccess && !isFail
  const showOrbs = (phase === 'invoke' || phase === 'orbit' || phase === 'fuse')
  const showSparks = isFull && (phase === 'fuse' || phase === 'sigil')
  const showSigil = phaseReach(phase, 'sigil') && !isFail
  const useDrivenOrbs = phase === 'orbit' || phase === 'fuse'
  const staticAngles = phase === 'invoke'

  const ariaLabel = isSuccess
    ? `${result?.name ?? 'Готово'}${result?.qty > 1 ? ` ×${result.qty}` : ''}`
    : isFail
      ? (recipe ? `${formatRecipeLine(recipe)} — не вышло` : 'Не вышло')
      : undefined

  const orbStyle = (angle) => ({
    '--orb-angle': `${angle}deg`,
    '--orb-scale': motion.scale,
    '--orb-opacity': motion.orbOpacity,
  })

  const angleA = staticAngles ? 0 : motion.angleA
  const angleB = staticAngles ? 180 : motion.angleB

  return (
    <div
      className={[
        'craft-ritual-layer',
        'craft-ritual-layer--flow',
        tierClass(performanceTier),
        `craft-ritual-layer--${phase}`,
        isFull ? 'craft-ritual-layer--showcase' : 'craft-ritual-layer--showcase craft-ritual-layer--showcase-compact',
        useDrivenOrbs ? 'craft-ritual-layer--driven' : '',
        staticAngles ? 'craft-ritual-layer--invoke-ready' : '',
        isSuccess ? 'craft-ritual-layer--quake-success' : '',
        isFail ? 'craft-ritual-layer--quake-fail' : '',
      ].filter(Boolean).join(' ')}
      style={{ '--orbit-period': `${periodMs}ms` }}
      aria-hidden={!isSuccess && !isFail}
      aria-label={ariaLabel}
    >
      <span className="craft-ritual-flash" />
      <span className="craft-ritual-mystery-veil" aria-hidden />
      <div className="craft-ritual-glow" />
      <div className="craft-ritual-glow craft-ritual-glow--secondary" />

      {phase === 'fuse' && isFull ? (
        <span className="craft-ritual-scan-beam" aria-hidden />
      ) : null}

      {showCircle ? (
        <div className="craft-ritual-circle craft-ritual-circle--flow">
          <div className="craft-ritual-circle-track" />
          {!isLite ? (
            <>
              <div className="craft-ritual-circle-track craft-ritual-circle-track--inner" />
              <div className="craft-ritual-circle-track craft-ritual-circle-track--dash" />
            </>
          ) : null}

          {showTicks ? (
            <div className="craft-ritual-tick-ring craft-ritual-flow-ticks" aria-hidden>
              {Array.from({ length: TICK_COUNT }, (_, index) => (
                <span
                  key={`tick-${index}`}
                  className="craft-ritual-tick"
                  style={{ '--ritual-i': index, '--ritual-n': TICK_COUNT }}
                />
              ))}
            </div>
          ) : null}

          {showOrbs ? (
            <>
              <div
                className={[
                  'craft-ritual-spinner',
                  'craft-ritual-spinner--a',
                  'craft-ritual-flow-orb',
                  useDrivenOrbs || staticAngles ? 'craft-ritual-spinner--driven' : '',
                ].filter(Boolean).join(' ')}
                style={(useDrivenOrbs || staticAngles) ? orbStyle(angleA) : undefined}
              >
                <span className="craft-ritual-orb craft-ritual-orb--driven">{slotA?.emoji ?? '·'}</span>
                {isFull ? <span className="craft-ritual-orb-glow" aria-hidden /> : null}
              </div>
              <div
                className={[
                  'craft-ritual-spinner',
                  'craft-ritual-spinner--b',
                  'craft-ritual-flow-orb',
                  useDrivenOrbs || staticAngles ? 'craft-ritual-spinner--driven' : '',
                ].filter(Boolean).join(' ')}
                style={(useDrivenOrbs || staticAngles) ? orbStyle(angleB) : undefined}
              >
                <span className="craft-ritual-orb craft-ritual-orb--driven">{slotB?.emoji ?? '·'}</span>
                {isFull ? <span className="craft-ritual-orb-glow" aria-hidden /> : null}
              </div>
            </>
          ) : null}

          {showSparks ? (
            <div className="craft-ritual-flow-sparks" aria-hidden>
              {Array.from({ length: SPARKS }, (_, index) => (
                <span
                  key={`fuse-spark-${index}`}
                  className="craft-ritual-fuse-spark"
                  style={{ '--ritual-i': index, '--ritual-n': SPARKS }}
                />
              ))}
            </div>
          ) : null}

          {isLite && phase === 'sigil' ? (
            <div className="craft-ritual-flow-sparks" aria-hidden>
              {Array.from({ length: LITE_SPARKS }, (_, index) => (
                <span
                  key={`lite-spark-${index}`}
                  className="craft-ritual-fuse-spark craft-ritual-fuse-spark--lite"
                  style={{ '--ritual-i': index, '--ritual-n': LITE_SPARKS }}
                />
              ))}
            </div>
          ) : null}

          {showSigil ? (
            <div className={`craft-ritual-sigil craft-ritual-sigil--flow ${isLite ? 'craft-ritual-sigil--lite' : ''}`}>
              <span className="craft-ritual-sigil-ring craft-ritual-sigil-ring--outer" aria-hidden />
              <span className="craft-ritual-sigil-ring craft-ritual-sigil-ring--mid" aria-hidden />
              <span className="craft-ritual-sigil-ring craft-ritual-sigil-ring--inner" aria-hidden />
              <span className="craft-ritual-sigil-core" aria-hidden />
              {result?.emoji ? (
                <span className="craft-ritual-ghost-result craft-ritual-flow-ghost" aria-hidden>
                  {result.emoji}
                </span>
              ) : null}
              {isFull ? (
                <>
                  <span className="craft-ritual-sigil-beam craft-ritual-sigil-beam--a" aria-hidden />
                  <span className="craft-ritual-sigil-beam craft-ritual-sigil-beam--b" aria-hidden />
                  <span className="craft-ritual-sigil-beam craft-ritual-sigil-beam--c" aria-hidden />
                </>
              ) : null}
              <span className="craft-ritual-sigil-pulse" aria-hidden />
            </div>
          ) : null}
        </div>
      ) : null}

      {isFail && isFull ? (
        <RitualCrumble slotA={slotA} slotB={slotB} variant="backdrop" />
      ) : null}

      {isFail && !isFull ? (
        <div className="craft-ritual-resolve craft-ritual-resolve--fail" aria-hidden>
          <RitualCrumble slotA={slotA} slotB={slotB} variant="compact" />
        </div>
      ) : null}

      {isSuccess && isFull ? Array.from({ length: EMBER_COUNT }, (_, index) => (
        <span
          key={`ember-${index}`}
          className="craft-ritual-ember"
          style={{ '--ritual-i': index, '--ritual-n': EMBER_COUNT }}
        />
      )) : null}

      {isSuccess && isLite ? Array.from({ length: 4 }, (_, index) => (
        <span
          key={`lite-ember-${index}`}
          className="craft-ritual-ember craft-ritual-ember--lite"
          style={{ '--ritual-i': index, '--ritual-n': 4 }}
        />
      )) : null}
    </div>
  )
})

export default CraftRitualEffect
