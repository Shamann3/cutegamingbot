import { useEffect, useState } from 'react'
import { useSettings } from '../context/SettingsContext'
import { isMobilePerfDevice } from '../utils/devicePerf'
import { useEquippedCosmetics } from '../hooks/useEquippedCosmetics'
import { SEASON_MODES } from '../constants/season'
import SeasonAtmosphere from './decor/SeasonAtmosphere'

/**
 * Фон: сезонный лес + лёгкие частицы.
 * По умолчанию — мало DOM/анимаций, чтобы не лагало даже на Full.
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
    ].join(', '),
    png: [
      '/assets/forest-bg.png 768w',
      '/assets/forest-bg-2x.png 1536w',
      '/assets/forest-bg-3x.png 2304w',
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

const FIREFLIES = Array.from({ length: 6 }, (_, i) => ({
  id: i,
  left: 10 + ((i * 23) % 78),
  top: 10 + ((i * 17) % 60),
  size: i % 3 === 0 ? 2.5 : 2,
  delay: (i * 0.7) % 4,
  duration: 5.5 + (i % 3) * 0.8,
  variant: i % 3,
}))

const SNOWFLAKES = Array.from({ length: 10 }, (_, i) => ({
  id: i,
  left: 4 + ((i * 19) % 92),
  size: 1.6 + (i % 3) * 0.6,
  delay: (i * 0.65) % 6,
  duration: 8 + (i % 4) * 1.2,
  drift: -10 + (i % 5) * 4,
}))

const MOBILE_FIREFLY_LIMIT = 3
const MOBILE_SNOW_LIMIT = 5

export default function FarmBackground({ variant = null }) {
  const { turboMode, season, liteMode } = useSettings()
  const { equipped } = useEquippedCosmetics()
  const v = variant ?? equipped.background?.code ?? null
  const [mobilePerf, setMobilePerf] = useState(isMobilePerfDevice)
  const [pageHidden, setPageHidden] = useState(
    typeof document !== 'undefined' ? document.hidden : false,
  )

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

  useEffect(() => {
    const onVis = () => setPageHidden(document.hidden)
    document.addEventListener('visibilitychange', onVis)
    return () => document.removeEventListener('visibilitychange', onVis)
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
  const showParticles = !liteMode && !pageHidden
  const showDecor = !liteMode && !mobilePerf && !pageHidden

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

      {summer && !mobilePerf && <div className="farm-bg-rays" />}
      {spring && <div className="farm-bg-spring-veil" />}
      {autumn && <div className="farm-bg-autumn-veil" />}
      {winter && <div className="farm-bg-frost" />}

      <div className="farm-bg-mist farm-bg-mist-a" />

      {showParticles && (
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
      )}

      {showDecor && <SeasonAtmosphere season={season} dense={false} />}

      <div className="farm-bg-shade-top" />
      <div className="farm-bg-shade-bottom" />
      <div className="farm-bg-vignette" />
      <div className="farm-bg-cosmetic-overlay" aria-hidden />
    </div>
  )
}
