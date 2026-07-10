import CountUp from './CountUp'

// Один цикл «удара» (QRS-подобный всплеск + меньшая T-волна), тайлится дважды
// для бесшовной прокрутки — .pulse-hero-vitals показывает первую половину,
// анимация сдвигает ровно на одну копию рисунка.
const BEAT_POINTS = [
  [0, 34], [34, 34], [42, 20], [50, 48], [58, 10], [66, 34],
  [84, 34], [92, 27], [100, 34], [134, 34],
]

function buildWavePoints(tiles) {
  const points = []
  for (let t = 0; t < tiles; t += 1) {
    for (const [x, y] of BEAT_POINTS) points.push(`${x + t * 134},${y}`)
  }
  return points.join(' ')
}

const WAVE_POINTS = buildWavePoints(2)

export default function PulseHero({ onlineNow, todayPeak, windowSeconds, loading }) {
  const hasValue = typeof onlineNow === 'number'

  return (
    <section className="panel-shelf panel-pulse-hero" aria-live="polite">
      <div className="pulse-hero-head">
        <p className="pulse-hero-eyebrow">
          <span className="panel-live-dot" aria-hidden="true" />
          Сейчас на ферме
        </p>
        <p className="pulse-hero-hint">
          {windowSeconds ? `Пинг 20 сек · grace ${windowSeconds} сек` : 'Heartbeat WebApp'}
        </p>
      </div>

      <div className="pulse-hero-body">
        <p className="pulse-hero-figure">
          {loading || !hasValue ? (
            <span className="pulse-hero-skeleton" aria-hidden="true" />
          ) : (
            <CountUp value={onlineNow} className="pulse-hero-value" />
          )}
          <span className="pulse-hero-unit">игроков онлайн</span>
        </p>

        <div className="pulse-hero-vitals" aria-hidden="true">
          <svg
            className="pulse-hero-wave"
            viewBox="0 0 268 60"
            preserveAspectRatio="none"
          >
            <polyline className="pulse-hero-wave-trace" points={WAVE_POINTS} />
          </svg>
        </div>
      </div>

      <p className="pulse-hero-foot">
        Пик сегодня — <strong>{loading ? '…' : (todayPeak ?? 0).toLocaleString('ru-RU')}</strong>
      </p>
    </section>
  )
}
