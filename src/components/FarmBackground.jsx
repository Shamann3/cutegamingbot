import { useEffect, useState } from 'react'
import { useSettings } from '../context/SettingsContext'
import { isMobilePerfDevice } from '../utils/devicePerf'
import { useEquippedCosmetics } from '../hooks/useEquippedCosmetics'

/**
 * Фон: SVG/арт леса + лёгкие анимации.
 * В турбо - только плоский градиент без картинки и частиц.
 */
const WEBP_SRCSET = [
  '/assets/forest-bg.webp 768w',
  '/assets/forest-bg-2x.webp 1536w',
  '/assets/forest-bg-3x.webp 2304w',
  '/assets/forest-bg-4k.webp 2880w',
].join(', ')

const PNG_SRCSET = [
  '/assets/forest-bg.png 768w',
  '/assets/forest-bg-2x.png 1536w',
  '/assets/forest-bg-3x.png 2304w',
  '/assets/forest-bg-4k.png 2880w',
].join(', ')

const FIREFLIES = Array.from({ length: 18 }, (_, i) => ({
  id: i,
  left: 8 + ((i * 19.1) % 84),
  top: 6 + ((i * 12.3) % 72),
  size: i % 4 === 0 ? 3 : 2,
  delay: (i * 0.42) % 5,
  duration: 4 + (i % 5) * 0.8,
  variant: i % 3,
}))

const SPARKS = Array.from({ length: 5 }, (_, i) => ({
  id: i,
  left: 15 + ((i * 28) % 70),
  top: 12 + ((i * 22) % 55),
  delay: i * 1.8,
  duration: 6 + (i % 2) * 2,
  rotate: -35 + (i % 4) * 20,
}))

const MUSHROOM_GLOWS = [
  { left: '6%', bottom: '10%', size: 100, delay: 0 },
  { left: '14%', bottom: '6%', size: 75, delay: 1.5 },
  { left: '78%', bottom: '12%', size: 60, delay: 0.6 },
]

const MOBILE_FIREFLY_LIMIT = 6
const MOBILE_SPARK_LIMIT = 2
const MOBILE_GLOW_LIMIT = 2

export default function FarmBackground({ variant = null }) {
  const { turboMode } = useSettings()
  const { equipped } = useEquippedCosmetics()
  // Equipped background applies on EVERY tab (each tab renders FarmBackground).
  // An explicit `variant` prop still overrides, if ever passed.
  const v = variant ?? equipped.background?.code ?? null
  const [mobilePerf, setMobilePerf] = useState(isMobilePerfDevice)

  useEffect(() => {
    const queries = [
      window.matchMedia('(hover: none) and (pointer: coarse)'),
      window.matchMedia('(max-width: 640px)'),
    ]
    const sync = () => setMobilePerf(isMobilePerfDevice())
    sync()
    queries.forEach((mq) => mq.addEventListener('change', sync))
    return () => queries.forEach((mq) => mq.removeEventListener('change', sync))
  }, [])

  if (turboMode) {
    return (
      <div
        className={`farm-bg-root farm-bg-root--turbo fixed inset-0 -z-10 overflow-hidden${v ? ` farm-bg--${v}` : ''}`}
        aria-hidden
      >
        <div className="farm-bg-cosmetic-overlay" aria-hidden />
      </div>
    )
  }

  const fireflies = mobilePerf ? FIREFLIES.slice(0, MOBILE_FIREFLY_LIMIT) : FIREFLIES
  const sparks = mobilePerf ? SPARKS.slice(0, MOBILE_SPARK_LIMIT) : SPARKS
  const glows = mobilePerf ? MUSHROOM_GLOWS.slice(0, MOBILE_GLOW_LIMIT) : MUSHROOM_GLOWS

  return (
    <div
      className={`farm-bg-root fixed inset-0 -z-10 overflow-hidden bg-[#061008]${mobilePerf ? ' farm-bg-root--mobile' : ''}${v ? ` farm-bg--${v}` : ''}`}
      aria-hidden
    >
      <div className="farm-bg-image-wrap">
        <picture className="farm-bg-picture">
          <source type="image/webp" srcSet={WEBP_SRCSET} sizes="100vw" />
          <img
            src="/assets/forest-bg.svg"
            srcSet={`${PNG_SRCSET}, /assets/forest-bg.svg 1200w`}
            sizes="100vw"
            alt=""
            draggable={false}
            className="farm-bg-image"
            decoding="async"
            fetchPriority="high"
          />
        </picture>
      </div>

      <div className="farm-bg-rays" />
      <div className="farm-bg-mist farm-bg-mist-a" />
      {!mobilePerf && <div className="farm-bg-mist farm-bg-mist-b" />}

      {glows.map((g, i) => (
        <div
          key={i}
          className="farm-bg-glow"
          style={{
            left: g.left,
            bottom: g.bottom,
            width: g.size,
            height: g.size,
            animationDelay: `${g.delay}s`,
          }}
        />
      ))}

      {sparks.map((s) => (
        <div
          key={s.id}
          className="farm-bg-spark"
          style={{
            left: `${s.left}%`,
            top: `${s.top}%`,
            '--spark-rotate': `${s.rotate}deg`,
            '--spark-dur': `${s.duration}s`,
            animationDelay: `${s.delay}s`,
          }}
        />
      ))}

      <div className="farm-bg-particles">
        {fireflies.map((f) => (
          <span
            key={f.id}
            className={`farm-bg-firefly farm-bg-firefly-${f.variant}`}
            style={{
              left: `${f.left}%`,
              top: `${f.top}%`,
              width: f.size,
              height: f.size,
              '--ff-dur': `${f.duration}s`,
              animationDelay: `${f.delay}s`,
            }}
          />
        ))}
      </div>

      <div className="farm-bg-shade-top" />
      <div className="farm-bg-shade-bottom" />
      <div className="farm-bg-vignette" />
      <div className="farm-bg-cosmetic-overlay" aria-hidden />
    </div>
  )
}
