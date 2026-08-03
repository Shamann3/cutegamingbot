import { useEffect, useState } from 'react'
import { useSettings } from '../../context/SettingsContext'
import { SEASON_MODES } from '../../constants/season'
import { isMobilePerfDevice } from '../../utils/devicePerf'
import '../../styles/globalSeason.css'

/**
 * Глобальный сезонный декор поверх всего приложения (все вкладки / модалки под ним).
 * Богатые SVG-детали: цветы, листья, гирлянды, ёлочки — не просто полоски.
 */

const SPRING_FLOWERS = Array.from({ length: 14 }, (_, i) => ({
  id: i,
  left: 2 + ((i * 7.2) % 96),
  bottom: i % 2 === 0 ? 1 + (i % 5) : 4 + (i % 4),
  scale: 0.55 + (i % 5) * 0.12,
  delay: (i * 0.4) % 4,
  hue: [330, 300, 20, 50, 340][i % 5],
  sway: 2.8 + (i % 4) * 0.4,
}))

const AUTUMN_LEAVES = Array.from({ length: 16 }, (_, i) => ({
  id: i,
  left: 3 + ((i * 6.1) % 94),
  size: 10 + (i % 4) * 3,
  delay: (i * 0.55) % 9,
  duration: 9 + (i % 5) * 1.4,
  drift: -36 + (i % 7) * 10,
  spin: 140 + (i % 4) * 80,
  tone: i % 4,
}))

const SUMMER_MOTES = Array.from({ length: 10 }, (_, i) => ({
  id: i,
  left: 8 + ((i * 9) % 84),
  top: 12 + ((i * 11) % 50),
  delay: (i * 0.7) % 5,
  duration: 6 + (i % 3),
}))

const WINTER_LIGHTS = Array.from({ length: 12 }, (_, i) => ({
  id: i,
  hue: [12, 48, 145, 200, 330, 30][i % 6],
  delay: (i * 0.28) % 2.8,
}))

function FlowerSvg({ hue }) {
  return (
    <svg viewBox="0 0 32 40" className="gsl-flower-svg" aria-hidden>
      <ellipse cx="16" cy="34" rx="2.2" ry="6" fill={`hsla(${hue}, 35%, 32%, 0.85)`} />
      {[0, 72, 144, 216, 288].map((rot) => (
        <ellipse
          key={rot}
          cx="16"
          cy="14"
          rx="5.5"
          ry="9"
          fill={`hsla(${hue}, 70%, 72%, 0.92)`}
          transform={`rotate(${rot} 16 16)`}
        />
      ))}
      <circle cx="16" cy="16" r="3.6" fill={`hsla(${hue + 40}, 85%, 62%, 0.95)`} />
      <circle cx="16" cy="16" r="1.5" fill="rgba(255,248,220,0.9)" />
    </svg>
  )
}

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

function TreeSvg({ side }) {
  return (
    <svg
      viewBox="0 0 48 72"
      className={`gsl-tree-svg gsl-tree-svg--${side}`}
      aria-hidden
    >
      <rect x="21" y="52" width="6" height="16" rx="1.5" fill="#5a3a22" />
      <polygon points="24,6 8,28 40,28" fill="#2f5c44" />
      <polygon points="24,16 6,40 42,40" fill="#3a7354" />
      <polygon points="24,28 4,54 44,54" fill="#2a4f3a" />
      <circle cx="18" cy="22" r="1.4" fill="#f0d78a" />
      <circle cx="28" cy="34" r="1.2" fill="#f87171" />
      <circle cx="22" cy="44" r="1.3" fill="#60a5fa" />
      <polygon points="24,4 22,8 26,8" fill="#e8c56a" />
      <ellipse cx="16" cy="18" rx="5" ry="2.2" fill="rgba(244,248,252,0.35)" />
      <ellipse cx="30" cy="32" rx="4" ry="1.8" fill="rgba(244,248,252,0.28)" />
    </svg>
  )
}

function SpringLayer({ dense }) {
  const flowers = dense ? SPRING_FLOWERS : SPRING_FLOWERS.slice(0, 8)
  return (
    <>
      <div className="gsl-spring-meadow" aria-hidden />
      <div className="gsl-spring-bloom-left" aria-hidden />
      <div className="gsl-spring-bloom-right" aria-hidden />
      <div className="gsl-ground-row">
        {flowers.map((f) => (
          <span
            key={f.id}
            className="gsl-flower"
            style={{
              left: `${f.left}%`,
              '--flower-lift': `${f.bottom * 0.35}rem`,
              '--gsl-scale': f.scale,
              '--gsl-delay': `${f.delay}s`,
              '--gsl-sway': `${f.sway}s`,
            }}
          >
            <FlowerSvg hue={f.hue} />
          </span>
        ))}
      </div>
    </>
  )
}

function SummerLayer({ dense }) {
  const motes = dense ? SUMMER_MOTES : SUMMER_MOTES.slice(0, 5)
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
      <div className="gsl-summer-grass" aria-hidden />
    </>
  )
}

function AutumnLayer({ dense }) {
  const leaves = dense ? AUTUMN_LEAVES : AUTUMN_LEAVES.slice(0, 9)
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
          <path d="M0,11 Q30,3 55,12 T100,7" fill="none" stroke="rgba(232,197,106,0.28)" strokeWidth="0.55" />
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
      <div className="gsl-tree gsl-tree--left" aria-hidden>
        <TreeSvg side="left" />
      </div>
      <div className="gsl-tree gsl-tree--right" aria-hidden>
        <TreeSvg side="right" />
      </div>
      <div className="gsl-winter-ground" aria-hidden />
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
