import { useEffect, useState } from 'react'
import { useSettings } from '../../context/SettingsContext'
import { SEASON_MODES } from '../../constants/season'
import { isMobilePerfDevice } from '../../utils/devicePerf'
import '../../styles/globalSeason.css'

/**
 * Глобальный сезонный декор на всех вкладках.
 * Только атмосфера сверху/по воздуху — без ёлочек/цветов/травы снизу.
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

const SUMMER_MOTES = Array.from({ length: 8 }, (_, i) => ({
  id: i,
  left: 10 + ((i * 10) % 80),
  top: 14 + ((i * 12) % 48),
  delay: (i * 0.7) % 5,
  duration: 6 + (i % 3),
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

function LeafSvg({ tone }) {
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
  const motes = dense ? SUMMER_MOTES : SUMMER_MOTES.slice(0, 4)
  return (
    <>
      <div className="gsl-summer-heat" aria-hidden />
      <div className="gsl-summer-canopy-l" aria-hidden />
      <div className="gsl-summer-canopy-r" aria-hidden />
      <div className="gsl-summer-sunburst" aria-hidden />
      {motes.map((m) => (
        <span
          key={m.id}
          className="gsl-summer-mote"
          style={{
            left: `${m.left}%`,
            top: `${m.top}%`,
            animationDelay: `${m.delay}s`,
            animationDuration: `${m.duration}s`,
          }}
        />
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
          <LeafSvg tone={l.tone} />
        </span>
      ))}
    </>
  )
}

function WinterLayer({ dense }) {
  const lights = dense ? WINTER_LIGHTS : WINTER_LIGHTS.slice(0, 8)
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
