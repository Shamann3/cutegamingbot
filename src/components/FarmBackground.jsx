import { useEffect, useState } from 'react'
import { useSettings } from '../context/SettingsContext'
import { isMobilePerfDevice } from '../utils/devicePerf'
import { useEquippedCosmetics } from '../hooks/useEquippedCosmetics'
import { SEASON_MODES } from '../constants/season'
import SeasonAtmosphere from './decor/SeasonAtmosphere'

/**
 * Фон: сезонный лес + частицы и декор.
 * В турбо — плоский градиент без картинки.
 */

function srcSet(prefix, ext) {
  return [
    `/assets/${prefix}.${ext} 768w`,
    `/assets/${prefix}-2x.${ext} 1536w`,
    `/assets/${prefix}-3x.${ext} 2304w`,
  ].join(', ')
}

const BG = {
  [SEASON_MODES.SPRING]: {
    webp: srcSet('forest-bg-spring', 'webp'),
    png: srcSet('forest-bg-spring', 'png'),
    fallback: '/assets/forest-bg-spring.png',
  },
  [SEASON_MODES.SUMMER]: {
    webp: [
      '/assets/forest-bg.webp 768w',
      '/assets/forest-bg-2x.webp 1536w',
      '/assets/forest-bg-3x.webp 2304w',
      '/assets/forest-bg-4k.webp 2880w',
    ].join(', '),
    png: [
      '/assets/forest-bg.png 768w',
      '/assets/forest-bg-2x.png 1536w',
      '/assets/forest-bg-3x.png 2304w',
      '/assets/forest-bg-4k.png 2880w',
    ].join(', '),
    fallback: '/assets/forest-bg.svg',
  },
  [SEASON_MODES.AUTUMN]: {
    webp: srcSet('forest-bg-autumn', 'webp'),
    png: srcSet('forest-bg-autumn', 'png'),
    fallback: '/assets/forest-bg-autumn.png',
  },
  [SEASON_MODES.WINTER]: {
    webp: srcSet('forest-bg-winter', 'webp'),
    png: srcSet('forest-bg-winter', 'png'),
    fallback: '/assets/forest-bg-winter.png',
  },
}

const FIREFLIES = Array.from({ length: 18 }, (_, i) => ({
  id: i,
  left: 8 + ((i * 19.1) % 84),
  top: 6 + ((i * 12.3) % 72),
  size: i % 4 === 0 ? 3 : 2,
  delay: (i * 0.42) % 5,
  duration: 4 + (i % 5) * 0.8,
  variant: i % 3,
}))

const SNOWFLAKES = Array.from({ length: 36 }, (_, i) => ({
  id: i,
  left: 2 + ((i * 13.7) % 96),
  size: 1.4 + (i % 5) * 0.75,
  delay: (i * 0.48) % 9,
  duration: 6.5 + (i % 7) * 1.15,
  drift: -18 + (i % 9) * 4,
  soft: i % 3 === 0,
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
const MOBILE_SNOW_LIMIT = 16
const MOBILE_SPARK_LIMIT = 2
const MOBILE_GLOW_LIMIT = 2

export default function FarmBackground({ variant = null }) {
  const { turboMode, season, liteMode } = useSettings()
  const { equipped } = useEquippedCosmetics()
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

  const seasonClass = `farm-bg-root--${season}`
  const assets = BG[season] || BG[SEASON_MODES.SUMMER]
  const winter = season === SEASON_MODES.WINTER
  const summer = season === SEASON_MODES.SUMMER
  const spring = season === SEASON_MODES.SPRING
  const autumn = season === SEASON_MODES.AUTUMN

  if (turboMode) {
    return (
      <div
        className={`farm-bg-root farm-bg-root--turbo fixed inset-0 -z-10 overflow-hidden ${seasonClass}${v ? ` farm-bg--${v}` : ''}`}
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
  const showDecor = !liteMode

  return (
    <div
      className={[
        'farm-bg-root fixed inset-0 -z-10 overflow-hidden bg-[#061008]',
        mobilePerf ? 'farm-bg-root--mobile' : '',
        seasonClass,
        v ? `farm-bg--${v}` : '',
      ].filter(Boolean).join(' ')}
      aria-hidden
    >
      <div className="farm-bg-image-wrap">
        <picture className="farm-bg-picture">
          <source type="image/webp" srcSet={assets.webp} sizes="100vw" />
          <img
            src={assets.fallback}
            srcSet={`${assets.png}${summer ? ', /assets/forest-bg.svg 1200w' : ''}`}
            sizes="100vw"
            alt=""
            draggable={false}
            className="farm-bg-image"
            decoding="async"
            fetchPriority="high"
          />
        </picture>
      </div>

      {summer && <div className="farm-bg-rays" />}
      {spring && <div className="farm-bg-spring-veil" />}
      {autumn && <div className="farm-bg-autumn-veil" />}
      {winter && <div className="farm-bg-frost" />}
      {winter && <div className="farm-bg-frost farm-bg-frost--edge" />}

      <div className="farm-bg-mist farm-bg-mist-a" />
      {!mobilePerf && <div className="farm-bg-mist farm-bg-mist-b" />}

      {summer && glows.map((g, i) => (
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

      {summer && sparks.map((s) => (
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
              className={`farm-bg-snow${f.soft ? ' farm-bg-snow--soft' : ''}`}
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
          : summer
            ? fireflies.map((f) => (
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
            ))
            : null}
      </div>

      {showDecor && (
        <SeasonAtmosphere season={season} dense={!mobilePerf} />
      )}

      <div className="farm-bg-shade-top" />
      <div className="farm-bg-shade-bottom" />
      <div className="farm-bg-vignette" />
      <div className="farm-bg-cosmetic-overlay" aria-hidden />
    </div>
  )
}
