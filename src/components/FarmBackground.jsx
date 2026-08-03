import { useEffect, useState } from 'react'
import { useSettings } from '../context/SettingsContext'
import { isMobilePerfDevice } from '../utils/devicePerf'
import { useEquippedCosmetics } from '../hooks/useEquippedCosmetics'
import { SEASON_MODES } from '../constants/season'

/**
 * Фон: летний / зимний лес + сезонные частицы.
 * В турбо — плоский градиент без картинки.
 */

const SUMMER_WEBP = [
  '/assets/forest-bg.webp 768w',
  '/assets/forest-bg-2x.webp 1536w',
  '/assets/forest-bg-3x.webp 2304w',
  '/assets/forest-bg-4k.webp 2880w',
].join(', ')

const SUMMER_PNG = [
  '/assets/forest-bg.png 768w',
  '/assets/forest-bg-2x.png 1536w',
  '/assets/forest-bg-3x.png 2304w',
  '/assets/forest-bg-4k.png 2880w',
].join(', ')

const WINTER_WEBP = [
  '/assets/forest-bg-winter.webp 768w',
  '/assets/forest-bg-winter-2x.webp 1536w',
  '/assets/forest-bg-winter-3x.webp 2304w',
  '/assets/forest-bg-winter-4k.webp 2880w',
].join(', ')

const WINTER_PNG = [
  '/assets/forest-bg-winter.png 768w',
  '/assets/forest-bg-winter-2x.png 1536w',
  '/assets/forest-bg-winter-3x.png 2304w',
  '/assets/forest-bg-winter-4k.png 2880w',
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

const SNOWFLAKES = Array.from({ length: 22 }, (_, i) => ({
  id: i,
  left: 4 + ((i * 17.3) % 92),
  size: 1.5 + (i % 4) * 0.7,
  delay: (i * 0.55) % 7,
  duration: 7 + (i % 6) * 1.1,
  drift: -12 + (i % 7) * 4,
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
const MOBILE_SNOW_LIMIT = 10
const MOBILE_SPARK_LIMIT = 2
const MOBILE_GLOW_LIMIT = 2

export default function FarmBackground({ variant = null }) {
  const { turboMode, season } = useSettings()
  const { equipped } = useEquippedCosmetics()
  const v = variant ?? equipped.background?.code ?? null
  const winter = season === SEASON_MODES.WINTER
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
        className={`farm-bg-root farm-bg-root--turbo fixed inset-0 -z-10 overflow-hidden${winter ? ' farm-bg-root--winter' : ' farm-bg-root--summer'}${v ? ` farm-bg--${v}` : ''}`}
        aria-hidden
      >
        <div className="farm-bg-cosmetic-overlay" aria-hidden />
      </div>
    )
  }

  const fireflies = mobilePerf ? FIREFLIES.slice(0, MOBILE_FIREFLY_LIMIT) : FIREFLIES
  const snow = mobilePerf ? SNOWFLAKES.slice(0, MOBILE_SNOW_LIMIT) : SNOWFLAKES
  const sparks = mobilePerf ? SPARKS.slice(0, MOBILE_SPARK_LIMIT) : SPARKS
  const glows = mobilePerf ? MUSHROOM_GLOWS.slice(0, MOBILE_GLOW_LIMIT) : MUSHROOM_GLOWS

  const webp = winter ? WINTER_WEBP : SUMMER_WEBP
  const png = winter ? WINTER_PNG : SUMMER_PNG
  const fallback = winter ? '/assets/forest-bg-winter.png' : '/assets/forest-bg.svg'

  return (
    <div
      className={[
        'farm-bg-root fixed inset-0 -z-10 overflow-hidden bg-[#061008]',
        mobilePerf ? 'farm-bg-root--mobile' : '',
        winter ? 'farm-bg-root--winter' : 'farm-bg-root--summer',
        v ? `farm-bg--${v}` : '',
      ].filter(Boolean).join(' ')}
      aria-hidden
    >
      <div className="farm-bg-image-wrap">
        <picture className="farm-bg-picture">
          <source type="image/webp" srcSet={webp} sizes="100vw" />
          <img
            src={fallback}
            srcSet={`${png}${winter ? '' : ', /assets/forest-bg.svg 1200w'}`}
            sizes="100vw"
            alt=""
            draggable={false}
            className="farm-bg-image"
            decoding="async"
            fetchPriority="high"
          />
        </picture>
      </div>

      {!winter && <div className="farm-bg-rays" />}
      {winter && <div className="farm-bg-frost" />}
      {winter && <div className="farm-bg-frost farm-bg-frost--edge" />}

      <div className="farm-bg-mist farm-bg-mist-a" />
      {!mobilePerf && <div className="farm-bg-mist farm-bg-mist-b" />}

      {!winter && glows.map((g, i) => (
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

      {!winter && sparks.map((s) => (
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
        {winter
          ? snow.map((f) => (
            <span
              key={f.id}
              className="farm-bg-snow"
              style={{
                left: `${f.left}%`,
                width: f.size,
                height: f.size,
                '--snow-dur': `${f.duration}s`,
                '--snow-drift': `${f.drift}px`,
                animationDelay: `${f.delay}s`,
              }}
            />
          ))
          : fireflies.map((f) => (
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
