import CountUp from './CountUp'

export default function StatShelfCard({ label, value, hint, loading, live, area, quiet }) {
  return (
    <article
      className={`panel-shelf panel-shelf-stat${live ? ' panel-shelf-stat-live' : ''}${area ? ` panel-shelf-${area}` : ''}${quiet ? ' panel-shelf-quiet' : ''}`}
    >
      <p className="panel-shelf-label">
        {label}
        {live && !loading && <span className="panel-live-dot" aria-hidden="true" />}
      </p>
      <p className="panel-stat-value">
        {loading
          ? <span className="skeleton-stat-val" aria-hidden="true" />
          : typeof value === 'number'
            ? <CountUp value={value} />
            : value}
      </p>
      {hint && (
        loading
          ? <span className="skeleton-hint" aria-hidden="true" />
          : <p className="panel-stat-hint">{hint}</p>
      )}
    </article>
  )
}
