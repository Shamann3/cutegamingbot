import { SEASON_MODES } from '../../constants/season'

/** Сезонный декор поверх фона леса (гирлянды, ёлки, лепестки, листья). */

const GARLAND_LIGHTS = Array.from({ length: 8 }, (_, i) => ({
  id: i,
  hue: [12, 48, 145, 200, 330][i % 5],
  delay: (i * 0.35) % 2.4,
}))

const TREES = [
  { id: 0, side: 'left', scale: 0.9, bottom: '2%', left: '1%' },
  { id: 2, side: 'right', scale: 0.85, bottom: '1%', right: '2%' },
]

const PETALS = Array.from({ length: 7 }, (_, i) => ({
  id: i,
  left: 8 + ((i * 22) % 84),
  size: 5 + (i % 3) * 2,
  delay: (i * 0.9) % 7,
  duration: 10 + (i % 3) * 1.5,
  drift: -24 + (i % 5) * 8,
  rotate: (i * 40) % 360,
  tone: i % 3,
}))

const LEAVES = Array.from({ length: 8 }, (_, i) => ({
  id: i,
  left: 6 + ((i * 20) % 88),
  size: 6 + (i % 3) * 2,
  delay: (i * 0.8) % 8,
  duration: 9 + (i % 3) * 1.3,
  drift: -30 + (i % 5) * 10,
  spin: 180 + (i % 3) * 90,
  tone: i % 4,
}))

function WinterDecor({ dense }) {
  const lights = dense ? GARLAND_LIGHTS : GARLAND_LIGHTS.slice(0, 5)
  const trees = TREES

  return (
    <>
      <div className="season-garland" aria-hidden>
        <svg className="season-garland-wire" viewBox="0 0 100 18" preserveAspectRatio="none">
          <path
            d="M0,6 Q25,16 50,7 T100,8"
            fill="none"
            stroke="rgba(232,197,106,0.35)"
            strokeWidth="0.6"
          />
          <path
            d="M0,9 Q30,2 55,11 T100,6"
            fill="none"
            stroke="rgba(158,201,232,0.22)"
            strokeWidth="0.45"
          />
        </svg>
        <div className="season-garland-lights">
          {lights.map((l) => (
            <span
              key={l.id}
              className="season-garland-bulb"
              style={{
                '--bulb-hue': l.hue,
                animationDelay: `${l.delay}s`,
              }}
            />
          ))}
        </div>
      </div>

      <div className="season-trees" aria-hidden>
        {trees.map((t) => (
          <span
            key={t.id}
            className={`season-tree season-tree--${t.side}`}
            style={{
              bottom: t.bottom,
              left: t.left,
              right: t.right,
              transform: `scale(${t.scale})`,
            }}
          >
            <span className="season-tree-trunk" />
            <span className="season-tree-cone season-tree-cone--a" />
            <span className="season-tree-cone season-tree-cone--b" />
            <span className="season-tree-cone season-tree-cone--c" />
            <span className="season-tree-star" />
            <span className="season-tree-snow" />
          </span>
        ))}
      </div>

      <div className="season-winter-ground" aria-hidden />
    </>
  )
}

function SpringDecor({ dense }) {
  const petals = dense ? PETALS : PETALS.slice(0, 4)
  return (
    <>
      <div className="season-bloom-haze" aria-hidden />
      <div className="season-particles" aria-hidden>
        {petals.map((p) => (
          <span
            key={p.id}
            className={`season-petal season-petal--${p.tone}`}
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
      </div>
      <div className="season-branch season-branch--left" aria-hidden />
      <div className="season-branch season-branch--right" aria-hidden />
    </>
  )
}

function AutumnDecor({ dense }) {
  const leaves = dense ? LEAVES : LEAVES.slice(0, 4)
  return (
    <>
      <div className="season-autumn-haze" aria-hidden />
      <div className="season-particles" aria-hidden>
        {leaves.map((l) => (
          <span
            key={l.id}
            className={`season-leaf season-leaf--${l.tone}`}
            style={{
              left: `${l.left}%`,
              width: l.size,
              height: l.size * 0.65,
              '--fall-dur': `${l.duration}s`,
              '--fall-drift': `${l.drift}px`,
              '--fall-spin': `${l.spin}deg`,
              animationDelay: `${l.delay}s`,
            }}
          />
        ))}
      </div>
      <div className="season-harvest-glow" aria-hidden />
    </>
  )
}

function SummerDecor() {
  return (
    <>
      <div className="season-summer-sun" aria-hidden />
      <div className="season-summer-haze" aria-hidden />
      <div className="season-summer-canopy season-summer-canopy--left" aria-hidden />
      <div className="season-summer-canopy season-summer-canopy--right" aria-hidden />
    </>
  )
}

export default function SeasonAtmosphere({ season, dense = true }) {
  if (season === SEASON_MODES.WINTER) return <WinterDecor dense={dense} />
  if (season === SEASON_MODES.SPRING) return <SpringDecor dense={dense} />
  if (season === SEASON_MODES.AUTUMN) return <AutumnDecor dense={dense} />
  if (season === SEASON_MODES.SUMMER) return <SummerDecor />
  return null
}
