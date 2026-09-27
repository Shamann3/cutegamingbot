function finite(value) {
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

function peakOf(points) {
  let max = 0
  for (const point of points) {
    const n = finite(point?.value)
    if (n != null && n > max) max = n
  }
  return max
}

function levelOf(value, max) {
  if (value == null || value <= 0 || max <= 0) return 0
  const t = value / max
  if (t < 0.25) return 1
  if (t < 0.5) return 2
  if (t < 0.75) return 3
  return 4
}

function Frame({ caption, children, empty }) {
  return (
    <figure className="sight" style={{ position: "relative" }}>
      {caption && <figcaption className="sight-caption">{caption}</figcaption>}
      {empty ? <p className="sight-empty">За этот отрезок ряда нет</p> : children}
    </figure>
  )
}

/** Часы или дни по кругу. Радиус точки — её величина, не случайное облако. */
export function PolarPlot({ points = [], center = '—', caption }) {
  const rows = points
    .map((point) => ({ label: point.label || '', value: finite(point.value) }))
    .filter((point) => point.value != null)
  const max = peakOf(rows)
  const alive = rows.some((point) => point.value > 0)
  const cx = 160
  const cy = 160
  const radius = 118

  return (
    <Frame caption={caption} empty={!rows.length}>
      <svg className="sight-polar" viewBox="0 0 320 320" role="img" aria-label={caption || 'Круговая диаграмма'}>
        {[0.25, 0.5, 0.75, 1].map((step) => (
          <circle key={step} cx={cx} cy={cy} r={radius * step} className="sight-ring" />
        ))}
        {rows.map((point, index) => {
          const angle = -Math.PI / 2 + (index / rows.length) * Math.PI * 2
          const x2 = cx + Math.cos(angle) * radius
          const y2 = cy + Math.sin(angle) * radius
          return <line key={point.label || index} x1={cx} y1={cy} x2={x2} y2={y2} className="sight-spoke" />
        })}
        {alive && rows.map((point, index) => {
          if (point.value <= 0) return null
          const angle = -Math.PI / 2 + (index / rows.length) * Math.PI * 2
          const reach = (point.value / max) * radius
          const x = cx + Math.cos(angle) * reach
          const y = cy + Math.sin(angle) * reach
          return (
            <circle
              key={`d-${point.label || index}`}
              cx={x}
              cy={y}
              r={point.value === max ? 5 : 3.2}
              className="sight-dot"
              onMouseEnter={(e) => {
                const host = e.currentTarget.closest('figure')
                if (!host) return
                let tip = host.querySelector('.sight-float-tip')
                if (!tip) {
                  tip = document.createElement('div')
                  tip.className = 'sight-float-tip'
                  host.appendChild(tip)
                }
                tip.textContent = `${point.label}: ${point.value}`
                tip.style.opacity = '1'
              }}
              onMouseMove={(e) => {
                const host = e.currentTarget.closest('figure')
                const tip = host?.querySelector('.sight-float-tip')
                if (!tip) return
                const rect = host.getBoundingClientRect()
                tip.style.left = `${e.clientX - rect.left + 10}px`
                tip.style.top = `${e.clientY - rect.top + 10}px`
              }}
              onMouseLeave={(e) => {
                const tip = e.currentTarget.closest('figure')?.querySelector('.sight-float-tip')
                if (tip) tip.style.opacity = '0'
              }}
            >
              <title>{`${point.label}: ${point.value}`}</title>
            </circle>
          )
        })}
        <text x={cx} y={cy + 6} textAnchor="middle" className="sight-center">{center}</text>
      </svg>
    </Frame>
  )
}

function weekdayLead(iso) {
  const date = new Date(`${iso}T12:00:00`)
  if (Number.isNaN(date.getTime())) return 0
  return (date.getDay() + 6) % 7
}

/** Сетка как календарь привычек: столбец — неделя, строка — день. Пустая клетка — не ноль в данных, а день вне ряда. */
export function HabitGrid({ points = [], caption, selected = '', onPick }) {
  const rows = points
    .map((point) => ({
      date: String(point.date || ''),
      label: point.label || String(point.date || ''),
      value: finite(point.value),
    }))
    .filter((point) => point.date && point.value != null)
  const dated = rows.length > 0 && rows.every((point) => /^\d{4}-\d{2}-\d{2}$/.test(point.date))
  const max = peakOf(rows)
  const lead = dated ? weekdayLead(rows[0].date) : 0
  const cells = [
    ...Array.from({ length: lead }, (_, index) => ({ key: `pad-${index}`, pad: true })),
    ...rows.map((point) => ({ ...point, key: point.date, pad: false })),
  ]

  return (
    <Frame caption={caption} empty={!rows.length}>
      <div className={`sight-habit-wrap${dated && cells.length > 21 ? ' is-scroll' : ''}`}>
        <div
          className={`sight-habit${dated ? ' is-weeks' : ''}`}
          role="list"
        >
          {cells.map((cell) => {
            if (cell.pad) return <span key={cell.key} className="sight-cell is-pad" />
            const level = levelOf(cell.value, max)
            const on = selected && selected === cell.date
            const Tag = onPick ? 'button' : 'span'
            return (
              <Tag
                key={cell.key}
                type={onPick ? 'button' : undefined}
                role="listitem"
                className={`sight-cell${on ? ' is-on' : ''}`}
                data-level={level}
                title={`${cell.label}: ${cell.value}`}
                aria-label={`${cell.label}: ${cell.value}`}
                aria-pressed={onPick ? on : undefined}
                onClick={onPick ? () => onPick(cell.date) : undefined}
              />
            )
          })}
        </div>
      </div>
    </Frame>
  )
}

function hexPoint(cx, cy, size) {
  return Array.from({ length: 6 }, (_, index) => {
    const angle = (Math.PI / 180) * (60 * index - 30)
    return `${cx + size * Math.cos(angle)},${cy + size * Math.sin(angle)}`
  }).join(' ')
}

/** Шестиугольники по дням. Яркость — число событий, не карта местности. */
export function HexHeat({ points = [], caption }) {
  const rows = points
    .map((point) => ({ label: point.label || '', value: finite(point.value) }))
    .filter((point) => point.value != null)
  const max = peakOf(rows)
  const cols = Math.min(10, Math.max(4, Math.ceil(Math.sqrt(rows.length || 1))))
  const size = 11
  const dx = size * 1.72
  const dy = size * 1.5
  const width = Math.ceil(cols * dx + size * 2)
  const height = Math.ceil(Math.ceil(rows.length / cols) * dy + size * 2)

  return (
    <Frame caption={caption} empty={!rows.length}>
      <svg className="sight-hex" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={caption || 'Тепловая карта'}>
        {rows.map((point, index) => {
          const col = index % cols
          const row = Math.floor(index / cols)
          const cx = size + 4 + col * dx + (row % 2 ? dx / 2 : 0)
          const cy = size + 4 + row * dy
          return (
            <polygon
              key={`${point.label}-${index}`}
              points={hexPoint(cx, cy, size - 1.2)}
              className="sight-hex-cell"
              data-level={levelOf(point.value, max)}
              onMouseEnter={(e) => {
                const host = e.currentTarget.closest('figure')
                if (!host) return
                let tip = host.querySelector('.sight-float-tip')
                if (!tip) {
                  tip = document.createElement('div')
                  tip.className = 'sight-float-tip'
                  host.appendChild(tip)
                }
                tip.textContent = `${point.label}: ${point.value}`
                tip.style.opacity = '1'
              }}
              onMouseMove={(e) => {
                const host = e.currentTarget.closest('figure')
                const tip = host?.querySelector('.sight-float-tip')
                if (!tip) return
                const rect = host.getBoundingClientRect()
                tip.style.left = `${e.clientX - rect.left + 10}px`
                tip.style.top = `${e.clientY - rect.top + 10}px`
              }}
              onMouseLeave={(e) => {
                const tip = e.currentTarget.closest('figure')?.querySelector('.sight-float-tip')
                if (tip) tip.style.opacity = '0'
              }}
            >
              <title>{`${point.label}: ${point.value}`}</title>
            </polygon>
          )
        })}
      </svg>
    </Frame>
  )
}

/** Свеча: фитиль от минимума до максимума, тело от открытия к закрытию. */
export function CandleChart({ rows = [], caption }) {
  const candles = rows
    .map((row) => ({
      label: row.label || '',
      low: finite(row.low),
      high: finite(row.high),
      open: finite(row.open),
      close: finite(row.close),
    }))
    .filter((row) => row.low != null && row.high != null && row.open != null && row.close != null)
  const low = Math.min(...candles.map((row) => row.low))
  const high = Math.max(...candles.map((row) => row.high))
  const span = high - low || 1
  const width = 640
  const height = 168
  const pad = 12
  const slot = candles.length ? (width - pad * 2) / candles.length : 0
  const y = (value) => pad + (1 - (value - low) / span) * (height - pad * 2)

  return (
    <Frame caption={caption} empty={!candles.length}>
      <svg className="sight-candles" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={caption || 'Свечи'}>
        {candles.map((row, index) => {
          const x = pad + index * slot + slot / 2
          const up = row.close >= row.open
          const bodyTop = y(Math.max(row.open, row.close))
          const bodyBot = y(Math.min(row.open, row.close))
          const body = Math.max(1.5, bodyBot - bodyTop)
          return (
            <g key={`${row.label}-${index}`} className={up ? 'is-up' : 'is-down'}>
              <title>{`${row.label}: от ${row.open} до ${row.close}, минимум ${row.low}, максимум ${row.high}`}</title>
              <line x1={x} x2={x} y1={y(row.high)} y2={y(row.low)} />
              <rect x={x - Math.min(5, slot * 0.28)} y={bodyTop} width={Math.min(10, slot * 0.56)} height={body} rx="1" />
            </g>
          )
        })}
      </svg>
    </Frame>
  )
}
