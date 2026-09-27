import { useCallback, useRef, useState } from 'react'

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

function fmtTipValue(value) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  return new Intl.NumberFormat('ru-RU').format(Number(value))
}

/** Общий плавающий тултип у курсора: дата/метка + значение. */
export function SightTip({ tip }) {
  if (!tip) return null
  return (
    <div
      className="sight-tip"
      style={{ left: tip.x, top: tip.y }}
      role="tooltip"
    >
      <strong>{tip.label}</strong>
      <span>{tip.valueText}</span>
    </div>
  )
}

export function useSightTip(rootRef) {
  const [tip, setTip] = useState(null)

  const show = useCallback((event, label, value) => {
    const root = rootRef?.current
    if (!root) return
    const rect = root.getBoundingClientRect()
    const pad = 10
    let x = event.clientX - rect.left + 12
    let y = event.clientY - rect.top - 8
    const maxX = Math.max(pad, rect.width - 140)
    const maxY = Math.max(pad, rect.height - 48)
    x = Math.max(pad, Math.min(x, maxX))
    y = Math.max(pad, Math.min(y, maxY))
    setTip({
      x,
      y,
      label: String(label || '—'),
      valueText: fmtTipValue(value),
    })
  }, [rootRef])

  const hide = useCallback(() => setTip(null), [])

  return { tip, show, hide }
}

function Frame({ caption, children, empty, tip }) {
  return (
    <figure className="sight">
      {caption && <figcaption className="sight-caption">{caption}</figcaption>}
      {empty ? <p className="sight-empty">За этот отрезок ряда нет</p> : (
        <div className="sight-body">
          {children}
          <SightTip tip={tip} />
        </div>
      )}
    </figure>
  )
}

/** Часы или дни по кругу. Радиус точки — её величина, не случайное облако. */
export function PolarPlot({ points = [], center = '—', caption }) {
  const rootRef = useRef(null)
  const { tip, show, hide } = useSightTip(rootRef)
  const rows = points
    .map((point) => ({ label: point.label || '', value: finite(point.value) }))
    .filter((point) => point.value != null)
  const max = peakOf(rows)
  const alive = rows.some((point) => point.value > 0)
  const cx = 160
  const cy = 160
  const radius = 118

  return (
    <Frame caption={caption} empty={!rows.length} tip={tip}>
      <div className="sight-body-inner" ref={rootRef}>
        <svg
          className="sight-polar"
          viewBox="0 0 320 320"
          role="img"
          aria-label={caption || 'Круговая диаграмма'}
          onPointerLeave={hide}
        >
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
                r={point.value === max ? 7 : 5}
                className="sight-dot"
                style={{ cursor: 'pointer' }}
                onPointerEnter={(e) => show(e, point.label, point.value)}
                onPointerMove={(e) => show(e, point.label, point.value)}
                onPointerLeave={hide}
              >
                <title>{`${point.label}: ${fmtTipValue(point.value)}`}</title>
              </circle>
            )
          })}
          <text x={cx} y={cy + 6} textAnchor="middle" className="sight-center">{center}</text>
        </svg>
      </div>
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
  const rootRef = useRef(null)
  const { tip, show, hide } = useSightTip(rootRef)
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
    <Frame caption={caption} empty={!rows.length} tip={tip}>
      <div className={`sight-habit-wrap${dated && cells.length > 21 ? ' is-scroll' : ''}`} ref={rootRef}>
        <div
          className={`sight-habit${dated ? ' is-weeks' : ''}`}
          role="list"
          onPointerLeave={hide}
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
                aria-label={`${cell.label}: ${fmtTipValue(cell.value)}`}
                aria-pressed={onPick ? on : undefined}
                onClick={onPick ? () => onPick(cell.date) : undefined}
                onPointerEnter={(e) => show(e, cell.label, cell.value)}
                onPointerMove={(e) => show(e, cell.label, cell.value)}
                onPointerLeave={hide}
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
  const rootRef = useRef(null)
  const { tip, show, hide } = useSightTip(rootRef)
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
    <Frame caption={caption} empty={!rows.length} tip={tip}>
      <div className="sight-body-inner" ref={rootRef}>
        <svg
          className="sight-hex"
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={caption || 'Тепловая карта'}
          onPointerLeave={hide}
        >
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
                style={{ cursor: 'pointer' }}
                onPointerEnter={(e) => show(e, point.label, point.value)}
                onPointerMove={(e) => show(e, point.label, point.value)}
                onPointerLeave={hide}
              >
                <title>{`${point.label}: ${fmtTipValue(point.value)}`}</title>
              </polygon>
            )
          })}
        </svg>
      </div>
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
