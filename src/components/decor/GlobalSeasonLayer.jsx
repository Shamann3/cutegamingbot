import { useEffect, useState } from 'react'
import { useSettings } from '../../context/SettingsContext'
import { SEASON_MODES } from '../../constants/season'
import { isMobilePerfDevice } from '../../utils/devicePerf'
import '../../styles/globalSeason.css'

/**
 * Глобальный сезонный декор на всех вкладках.
 * Лето — зелёные листья; зима — снежинки; без нижних ёлочек/травы.
 */

const AUTUMN_LEAVES = Array.from({ length: 14 }, (_, i) => ({
  id: i,
  left: 3 + ((i * 6.5) % 94),
  size: 10 + (i % 4) * 3,
  delay: (i * 0.55) % 9,
  duration: 9 + (i % 5) * 1.4,
  drift: -36 + (i % 7) * 10,
  spin: 140 + (i % 4) * 80,
  tone: i % 4,
}))

const SUMMER_LEAVES = Array.from({ length: 12 }, (_, i) => ({
  id: i,
  left: 4 + ((i * 7.8) % 92),
  size: 8 + (i % 3) * 2.5,
  delay: (i * 0.85) % 10,
  duration: 11 + (i % 4) * 1.6,
  drift: -28 + (i % 6) * 9,
  spin: 120 + (i % 4) * 70,
  tone: i % 3,
}))

const SUMMER_MOTES = Array.from({ length: 6 }, (_, i) => ({
  id: i,
  left: 12 + ((i * 12) % 76),
  top: 16 + ((i * 13) % 44),
  delay: (i * 0.8) % 5,
  duration: 6.5 + (i % 3),
}))

const SNOWFLAKES = Array.from({ length: 18 }, (_, i) => ({
  id: i,
  left: 2 + ((i * 5.4) % 96),
  size: 2 + (i % 4) * 1.1,
  delay: (i * 0.45) % 8,
  duration: 8 + (i % 5) * 1.5,
  drift: -18 + (i % 7) * 6,
  soft: i % 3 === 0,
}))

const WINTER_LIGHTS = Array.from({ length: 12 }, (_, i) => ({
  id: i,
  hue: [12, 48, 145, 200, 330, 30][i % 6],
  delay: (i * 0.28) % 2.8,
}))

const SPRING_PETALS = Array.from({ length: 10 }, (_, i) => ({
  id: i,
  left: 6 + ((i * 9) % 88),
  size: 7 + (i % 3) * 2,
  delay: (i * 0.7) % 7,
  duration: 10 + (i % 3) * 1.4,
  drift: -22 + (i % 5) * 8,
  rotate: (i * 36) % 360,
  tone: i % 3,
}))

function AutumnLeafSvg({ tone }) {
  const fills = ['#e0a04a', '#c45c30', '#d4a017', '#b87333']
  return (
    <svg viewBox="0 0 24 28" className="gsl-leaf-svg" aria-hidden>
      <path
        d="M12 2 C18 8 22 14 12 26 C2 14 6 8 12 2 Z"
        fill={fills[tone % fills.length]}
        opacity="0.92"
      />
      <path d="M12 6 L12 22" stroke="rgba(60,30,10,0.35)" strokeWidth="1" fill="none" />
    </svg>
  )
}

function GreenLeafSvg({ tone }) {
  const fills = ['#6aaf70', '#4a9a58', '#8fc48a']
  return (
    <svg viewBox="0 0 24 28" className="gsl-leaf-svg" aria-hidden>
      <path
        d="M12 2 C18 8 22 14 12 26 C2 14 6 8 12 2 Z"
        fill={fills[tone % fills.length]}
        opacity="0.88"
      />
      <path d="M12 6 L12 22" stroke="rgba(20,50,28,0.4)" strokeWidth="1" fill="none" />
    </svg>
  )
}

function SnowflakeSvg() {
  return (
    <svg viewBox="0 0 16 16" className="gsl-snow-svg" aria-hidden>
      <g stroke="rgba(240,248,255,0.92)" strokeWidth="1.1" strokeLinecap="round">
        <line x1="8" y1="1" x2="8" y2="15" />
        <line x1="1" y1="8" x2="15" y2="8" />
        <line x1="3" y1="3" x2="13" y2="13" />
        <line x1="13" y1="3" x2="3" y2="13" />
      </g>
      <circle cx="8" cy="8" r="1.2" fill="rgba(255,255,255,0.95)" />
    </svg>
  )
}

function SpringLayer({ dense }) {
  const petals = dense ? SPRING_PETALS : SPRING_PETALS.slice(0, 5)
  return (
    <>
      <div className="gsl-spring-bloom-left" aria-hidden />
      <div className="gsl-spring-bloom-right" aria-hidden />
      {petals.map((p) => (
        <span
          key={p.id}
          className={`gsl-spring-petal gsl-spring-petal--${p.tone}`}
          style={{
            left: `${p.left}%`,
            width: p.size,
            height: p.size * 0.7,
            '--fall-dur': `${p.duration}s`,
            '--fall-drift': `${p.drift}px`,
            '--fall-rot': `${p.rotate}deg`,
            animationDelay: `${p.delay}s`,
          }}
        />
      ))}
    </>
  )
}

function SummerLayer({ dense }) {
  const leaves = dense ? SUMMER_LEAVES : SUMMER_LEAVES.slice(0, 6)
  const motes = dense ? SUMMER_MOTES : SUMMER_MOTES.slice(0, 3)
  return (
    <>
      <div className="gsl-summer-heat" aria-hidden />
      <div className="gsl-summer-canopy-l" aria-hidden />
      <div className="gsl-summer-canopy-r" aria-hidden />
      <div className="gsl-summer-sunburst" aria-hidden />
      {motes.map((m) => (
        <span
          key={`m-${m.id}`}
          className="gsl-summer-mote"
          style={{
            left: `${m.left}%`,
            top: `${m.top}%`,
            animationDelay: `${m.delay}s`,
            animationDuration: `${m.duration}s`,
          }}
        />
      ))}
      {leaves.map((l) => (
        <span
          key={`l-${l.id}`}
          className="gsl-fall-leaf gsl-summer-leaf"
          style={{
            left: `${l.left}%`,
            width: l.size,
            height: l.size * 1.15,
            '--fall-dur': `${l.duration}s`,
            '--fall-drift': `${l.drift}px`,
            '--fall-spin': `${l.spin}deg`,
            animationDelay: `${l.delay}s`,
          }}
        >
          <GreenLeafSvg tone={l.tone} />
        </span>
      ))}
    </>
  )
}

function AutumnLayer({ dense }) {
  const leaves = dense ? AUTUMN_LEAVES : AUTUMN_LEAVES.slice(0, 8)
  return (
    <>
      <div className="gsl-autumn-haze" aria-hidden />
      <div className="gsl-autumn-edge-l" aria-hidden />
      <div className="gsl-autumn-edge-r" aria-hidden />
      {leaves.map((l) => (
        <span
          key={l.id}
          className="gsl-fall-leaf"
          style={{
            left: `${l.left}%`,
            width: l.size,
            height: l.size * 1.15,
            '--fall-dur': `${l.duration}s`,
            '--fall-drift': `${l.drift}px`,
            '--fall-spin': `${l.spin}deg`,
            animationDelay: `${l.delay}s`,
          }}
        >
          <AutumnLeafSvg tone={l.tone} />
        </span>
      ))}
    </>
  )
}

function WinterLayer({ dense }) {
  const lights = dense ? WINTER_LIGHTS : WINTER_LIGHTS.slice(0, 8)
  const snow = dense ? SNOWFLAKES : SNOWFLAKES.slice(0, 10)
  return (
    <>
      <div className="gsl-winter-frost" aria-hidden />
      <div className="gsl-garland" aria-hidden>
        <svg className="gsl-garland-wire" viewBox="0 0 100 20" preserveAspectRatio="none">
          <path d="M0,7 Q25,18 50,8 T100,9" fill="none" stroke="rgba(200,220,240,0.35)" strokeWidth="0.7" />
          <path d="M0,11 Q30,3 55,12 T100,7" fill="none" stroke="rgba(180,200,160,0.22)" strokeWidth="0.55" />
        </svg>
        <div className="gsl-garland-bulbs">
          {lights.map((l) => (
            <span
              key={l.id}
              className="gsl-bulb"
              style={{
                '--bulb-hue': l.hue,
                animationDelay: `${l.delay}s`,
              }}
            />
          ))}
        </div>
      </div>
      {snow.map((f) => (
        <span
          key={f.id}
          className={`gsl-snowflake${f.soft ? ' gsl-snowflake--soft' : ''}`}
          style={{
            left: `${f.left}%`,
            width: f.size * (f.soft ? 1 : 3.2),
            height: f.size * (f.soft ? 1 : 3.2),
            '--snow-dur': `${f.duration}s`,
            '--snow-drift': `${f.drift}px`,
            animationDelay: `${f.delay}s`,
          }}
        >
          {f.soft ? null : <SnowflakeSvg />}
        </span>
      ))}
    </>
  )
}

export default function GlobalSeasonLayer() {
  const { season, liteMode, turboMode } = useSettings()
  const [mobile, setMobile] = useState(isMobilePerfDevice)
  const [hidden, setHidden] = useState(
    typeof document !== 'undefined' ? document.hidden : false,
  )

  useEffect(() => {
    const sync = () => setMobile(isMobilePerfDevice())
    sync()
    window.addEventListener('resize', sync)
    return () => window.removeEventListener('resize', sync)
  }, [])

  useEffect(() => {
    const onVis = () => setHidden(document.hidden)
    document.addEventListener('visibilitychange', onVis)
    return () => document.removeEventListener('visibilitychange', onVis)
  }, [])

  if (turboMode || hidden) return null

  const dense = !liteMode && !mobile

  return (
    <div className={`gsl-root gsl-root--${season}`} aria-hidden>
      {season === SEASON_MODES.SPRING && <SpringLayer dense={dense} />}
      {season === SEASON_MODES.SUMMER && <SummerLayer dense={dense} />}
      {season === SEASON_MODES.AUTUMN && <AutumnLayer dense={dense} />}
      {season === SEASON_MODES.WINTER && <WinterLayer dense={dense} />}
    </div>
  )
}
