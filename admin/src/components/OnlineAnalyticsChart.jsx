import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

const CHART_W = 1000
const CHART_H = 300
const PAD = { top: 28, right: 18, bottom: 42, left: 52 }
const MINI_H = 56
const DRAG_THRESHOLD = 4

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function niceTicks(max, count = 4) {
  if (max <= 0) return [0]
  const rough = max / count
  const mag = 10 ** Math.floor(Math.log10(rough))
  const step = Math.ceil(rough / mag) * mag
  const ticks = []
  for (let v = 0; v <= max + step * 0.01; v += step) {
    ticks.push(Math.round(v))
    if (ticks.length > 8) break
  }
  if (ticks[ticks.length - 1] < max) ticks.push(Math.round(max))
  return ticks
}

function defaultVisibleSize(count, granularity) {
  if (count <= 1) return 1
  if (granularity === 'hour') return Math.min(count, 12)
  if (count <= 8) return count
  return Math.min(count, Math.max(7, Math.ceil(count * 0.45)))
}

function seriesPath(items, key, maxY, width, height, padLeft, padTop) {
  if (!items.length) return ''
  const innerW = width - padLeft - PAD.right
  const innerH = height - padTop - PAD.bottom
  const step = items.length <= 1 ? 0 : innerW / (items.length - 1)
  return items
    .map((item, index) => {
      const ratio = maxY > 0 ? item[key] / maxY : 0
      const x = padLeft + index * step
      const y = padTop + (1 - ratio) * innerH
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
    })
    .join(' ')
}

function pointX(index, total, innerW, padLeft) {
  if (total <= 1) return padLeft
  return padLeft + (index / (total - 1)) * innerW
}

function plotMetrics(rect) {
  const plotLeft = rect.left + (PAD.left / CHART_W) * rect.width
  const plotRight = rect.right - (PAD.right / CHART_W) * rect.width
  const plotWidth = Math.max(1, plotRight - plotLeft)
  return { plotLeft, plotRight, plotWidth }
}

export default function OnlineAnalyticsChart({
  points,
  granularity = 'hour',
  loading = false,
}) {
  const count = points.length
  const stageRef = useRef(null)
  const overlayRef = useRef(null)
  const dragRef = useRef(null)
  const rafRef = useRef(null)
  const viewRef = useRef({ start: 0, size: count || 1 })

  const [viewStart, setViewStart] = useState(0)
  const [viewSize, setViewSize] = useState(() => defaultVisibleSize(count, granularity))
  const [hoverIndex, setHoverIndex] = useState(null)
  const [pinnedIndex, setPinnedIndex] = useState(null)
  const [isDragging, setIsDragging] = useState(false)

  const setView = useCallback((start, size) => {
    const maxStart = Math.max(0, count - size)
    const nextStart = clamp(start, 0, maxStart)
    const nextSize = clamp(size, 2, count)
    viewRef.current = { start: nextStart, size: nextSize }
    setViewStart(nextStart)
    setViewSize(nextSize)
  }, [count])

  useEffect(() => {
    const size = defaultVisibleSize(count, granularity)
    const start = Math.max(0, count - size)
    viewRef.current = { start, size }
    setViewStart(start)
    setViewSize(size)
    setHoverIndex(null)
    setPinnedIndex(null)
  }, [count, granularity, points[0]?.id])

  const maxStart = Math.max(0, count - viewSize)
  const visibleStart = clamp(Math.floor(viewStart + 0.0001), 0, maxStart)
  const visibleEnd = Math.min(count - 1, visibleStart + viewSize - 1)
  const visiblePoints = useMemo(
    () => points.slice(visibleStart, visibleEnd + 1),
    [points, visibleStart, visibleEnd],
  )

  const maxValue = useMemo(
    () => Math.max(...points.map((p) => Math.max(p.peak, p.avg)), 1),
    [points],
  )
  const yTicks = useMemo(() => niceTicks(maxValue), [maxValue])

  const innerW = CHART_W - PAD.left - PAD.right
  const innerH = CHART_H - PAD.top - PAD.bottom

  const peakPath = seriesPath(visiblePoints, 'peak', maxValue, CHART_W, CHART_H, PAD.left, PAD.top)
  const avgPath = seriesPath(visiblePoints, 'avg', maxValue, CHART_W, CHART_H, PAD.left, PAD.top)
  const areaPath = peakPath
    ? `${peakPath} L ${(PAD.left + innerW).toFixed(2)} ${(PAD.top + innerH).toFixed(2)} L ${PAD.left} ${(PAD.top + innerH).toFixed(2)} Z`
    : ''

  const miniPeakPath = seriesPath(points, 'peak', maxValue, CHART_W, MINI_H, 12, 10)

  const activeIndex = pinnedIndex ?? hoverIndex
  const activePoint = activeIndex != null ? points[activeIndex] : null
  const isZoomed = viewStart > 0.01 || viewSize < count - 0.5

  const indexFromClientX = useCallback((clientX) => {
    const el = overlayRef.current
    if (!el || visiblePoints.length === 0) return null
    const rect = el.getBoundingClientRect()
    const { plotLeft, plotWidth } = plotMetrics(rect)
    const ratio = clamp((clientX - plotLeft) / plotWidth, 0, 1)
    const localIdx = visiblePoints.length <= 1
      ? 0
      : Math.round(ratio * (visiblePoints.length - 1))
    return visibleStart + localIdx
  }, [visiblePoints.length, visibleStart])

  const scheduleView = useCallback((start, size) => {
    viewRef.current = { start, size }
    if (rafRef.current != null) return
    rafRef.current = window.requestAnimationFrame(() => {
      rafRef.current = null
      const maxS = Math.max(0, count - viewRef.current.size)
      setViewStart(clamp(viewRef.current.start, 0, maxS))
      setViewSize(clamp(viewRef.current.size, 2, count))
    })
  }, [count])

  const zoomAt = useCallback((clientX, factor) => {
    const el = overlayRef.current
    if (!el || count < 3) return
    const rect = el.getBoundingClientRect()
    const { plotLeft, plotWidth } = plotMetrics(rect)
    const cursorRatio = clamp((clientX - plotLeft) / plotWidth, 0, 1)
    const { start, size } = viewRef.current
    const cursorIdx = start + cursorRatio * Math.max(size - 1, 0)
    const minSize = granularity === 'hour' ? 4 : 3
    const nextSize = clamp(Math.round(size * factor), minSize, count)
    const nextStart = clamp(cursorIdx - cursorRatio * (nextSize - 1), 0, count - nextSize)
    scheduleView(nextStart, nextSize)
  }, [count, granularity, scheduleView])

  useEffect(() => {
    const el = overlayRef.current
    if (!el) return undefined

    const onWheel = (e) => {
      e.preventDefault()
      e.stopPropagation()
      const factor = e.deltaY > 0 ? 1.1 : 0.9
      zoomAt(e.clientX, factor)
    }

    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [zoomAt, loading, count])

  useEffect(() => () => {
    if (rafRef.current != null) window.cancelAnimationFrame(rafRef.current)
  }, [])

  const onOverlayPointerDown = (e) => {
    if (e.button !== 0) return
    e.preventDefault()
    overlayRef.current?.setPointerCapture(e.pointerId)
    dragRef.current = {
      pointerId: e.pointerId,
      x: e.clientX,
      start: viewRef.current.start,
      moved: false,
    }
    setIsDragging(false)
  }

  const onOverlayPointerMove = (e) => {
    const drag = dragRef.current
    if (drag && drag.pointerId === e.pointerId) {
      const dx = e.clientX - drag.x
      if (!drag.moved && Math.abs(dx) >= DRAG_THRESHOLD) {
        drag.moved = true
        setIsDragging(true)
        setHoverIndex(null)
      }
      if (drag.moved) {
        e.preventDefault()
        const el = overlayRef.current
        if (!el) return
        const rect = el.getBoundingClientRect()
        const { plotWidth } = plotMetrics(rect)
        const idxPerPx = viewRef.current.size / plotWidth
        scheduleView(drag.start - dx * idxPerPx, viewRef.current.size)
      }
      return
    }
    setHoverIndex(indexFromClientX(e.clientX))
  }

  const onOverlayPointerUp = (e) => {
    const drag = dragRef.current
    if (drag && drag.pointerId === e.pointerId) {
      if (!drag.moved) {
        const idx = indexFromClientX(e.clientX)
        setPinnedIndex((prev) => (prev === idx ? null : idx))
      }
      dragRef.current = null
      setIsDragging(false)
      overlayRef.current?.releasePointerCapture(e.pointerId)
    }
  }

  const onOverlayPointerLeave = () => {
    if (!dragRef.current) setHoverIndex(null)
  }

  const resetView = () => {
    const size = defaultVisibleSize(count, granularity)
    const start = Math.max(0, count - size)
    setView(start, size)
    setPinnedIndex(null)
    setHoverIndex(null)
  }

  const showAll = () => {
    setView(0, count)
    setPinnedIndex(null)
    setHoverIndex(null)
  }

  const handleMinimapPointer = (clientX, el, mode) => {
    const rect = el.getBoundingClientRect()
    const ratio = clamp((clientX - rect.left) / rect.width, 0, 1)
    const center = ratio * Math.max(count - 1, 0)
    const { size } = viewRef.current
    const nextStart = clamp(center - size / 2, 0, maxStart)
    if (mode === 'jump') setView(nextStart, size)
    return nextStart
  }

  const zoomCenter = useCallback((factor) => {
    const el = overlayRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    zoomAt(rect.left + rect.width / 2, factor)
  }, [zoomAt])

  const onMinimapDown = (e) => {
    e.preventDefault()
    e.stopPropagation()
    const el = e.currentTarget
    el.setPointerCapture(e.pointerId)
    dragRef.current = {
      pointerId: e.pointerId,
      x: e.clientX,
      start: viewRef.current.start,
      moved: false,
      mode: 'minimap',
      el,
    }
    handleMinimapPointer(e.clientX, el, 'jump')
  }

  const onMinimapMove = (e) => {
    const drag = dragRef.current
    if (!drag || drag.mode !== 'minimap' || drag.pointerId !== e.pointerId) return
    drag.moved = true
    handleMinimapPointer(e.clientX, drag.el, 'jump')
  }

  const onMinimapUp = (e) => {
    const drag = dragRef.current
    if (drag?.mode === 'minimap' && drag.pointerId === e.pointerId) {
      dragRef.current = null
      e.currentTarget.releasePointerCapture(e.pointerId)
    }
  }

  const xLabelStep = Math.max(1, Math.ceil(visiblePoints.length / 6))
  const crosshairLocalIdx = activeIndex != null ? activeIndex - visibleStart : null
  const crosshairX = crosshairLocalIdx != null
    ? pointX(crosshairLocalIdx, visiblePoints.length, innerW, PAD.left)
    : null

  const viewportLeftPct = count <= 1 ? 0 : (viewStart / Math.max(count - 1, 1)) * 100
  const viewportWidthPct = count <= 1 ? 100 : ((viewSize - 1) / Math.max(count - 1, 1)) * 100

  if (loading) {
    return (
      <div className="online-chart online-chart-loading">
        <div className="panel-online-chart-skeleton" aria-hidden="true">
          <div className="panel-online-skeleton-bars" />
        </div>
      </div>
    )
  }

  if (!count) return null

  return (
    <div className="online-chart">
      <div className="online-chart-toolbar">
        <div className="online-chart-hints">
          <span>Колёсико — масштаб</span>
          <span>·</span>
          <span>Тянуть — листать</span>
          <span>·</span>
          <span>Клик — закрепить точку</span>
        </div>
        <div className="online-chart-toolbar-actions">
          <button type="button" className="online-chart-zoom-btn" onClick={() => zoomCenter(0.85)} aria-label="Приблизить">
            +
          </button>
          <button type="button" className="online-chart-zoom-btn" onClick={() => zoomCenter(1.15)} aria-label="Отдалить">
            −
          </button>
          {viewSize < count && (
            <button type="button" className="online-chart-reset" onClick={showAll}>
              Весь период
            </button>
          )}
          {isZoomed && (
            <button type="button" className="online-chart-reset" onClick={resetView}>
              Сбросить
            </button>
          )}
        </div>
      </div>

      <div ref={stageRef} className="online-chart-stage">
        <svg
          className="online-chart-svg"
          viewBox={`0 0 ${CHART_W} ${CHART_H}`}
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <defs>
            <linearGradient id="onlineChartArea" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgba(229, 229, 229, 0.32)" />
              <stop offset="100%" stopColor="rgba(229, 229, 229, 0.02)" />
            </linearGradient>
            <linearGradient id="onlineChartLine" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#f5f5f5" />
              <stop offset="50%" stopColor="#d4d4d4" />
              <stop offset="100%" stopColor="#a3a3a3" />
            </linearGradient>
          </defs>

          {yTicks.map((tick) => {
            const y = PAD.top + (1 - tick / maxValue) * innerH
            return (
              <g key={tick} pointerEvents="none">
                <line x1={PAD.left} y1={y} x2={CHART_W - PAD.right} y2={y} className="online-chart-grid" />
                <text x={PAD.left - 10} y={y + 4} className="online-chart-axis-y">{tick}</text>
              </g>
            )
          })}

          {areaPath && <path d={areaPath} fill="url(#onlineChartArea)" pointerEvents="none" />}
          {avgPath && <path d={avgPath} fill="none" className="online-chart-avg-line" strokeWidth="2" pointerEvents="none" />}
          {peakPath && (
            <path
              d={peakPath}
              fill="none"
              stroke="url(#onlineChartLine)"
              strokeWidth="2.75"
              strokeLinecap="round"
              strokeLinejoin="round"
              pointerEvents="none"
            />
          )}

          {visiblePoints.map((point, index) => {
            const globalIdx = visibleStart + index
            const isActive = activeIndex === globalIdx
            const showDot = point.isCurrent || point.isPeak || isActive || point.peak > 0
            if (!showDot) return null
            const x = pointX(index, visiblePoints.length, innerW, PAD.left)
            const ratio = maxValue > 0 ? point.peak / maxValue : 0
            const y = PAD.top + (1 - ratio) * innerH
            return (
              <circle
                key={point.id}
                cx={x}
                cy={y}
                r={isActive ? 6 : point.isPeak ? 5 : point.isCurrent ? 4.5 : 3}
                pointerEvents="none"
                className={[
                  'online-chart-dot',
                  isActive ? 'online-chart-dot-active' : '',
                  point.isCurrent ? 'online-chart-dot-current' : '',
                  point.isPeak ? 'online-chart-dot-peak' : '',
                ].filter(Boolean).join(' ')}
              />
            )
          })}

          {crosshairX != null && activePoint && (
            <g pointerEvents="none">
              <line x1={crosshairX} y1={PAD.top} x2={crosshairX} y2={PAD.top + innerH} className="online-chart-crosshair" />
              <circle
                cx={crosshairX}
                cy={PAD.top + (1 - activePoint.peak / maxValue) * innerH}
                r="7"
                className="online-chart-crosshair-dot"
              />
            </g>
          )}

          {visiblePoints.map((point, index) => {
            if (index % xLabelStep !== 0 && index !== visiblePoints.length - 1) return null
            const x = pointX(index, visiblePoints.length, innerW, PAD.left)
            return (
              <text key={`x-${point.id}`} x={x} y={CHART_H - 12} className="online-chart-axis-x" pointerEvents="none">
                {point.shortLabel || point.label}
              </text>
            )
          })}
        </svg>

        <div
          ref={overlayRef}
          className={`online-chart-overlay${isDragging ? ' online-chart-overlay-dragging' : ''}`}
          onPointerDown={onOverlayPointerDown}
          onPointerMove={onOverlayPointerMove}
          onPointerUp={onOverlayPointerUp}
          onPointerCancel={onOverlayPointerUp}
          onPointerLeave={onOverlayPointerLeave}
          role="presentation"
        />

        {activePoint && crosshairX != null && (
          <div
            className="online-chart-tooltip"
            style={{ left: `${((crosshairX / CHART_W) * 100).toFixed(2)}%` }}
          >
            <span className="online-chart-tooltip-label">{activePoint.label}</span>
            <span className="online-chart-tooltip-metric">
              пик <strong>{activePoint.peak.toLocaleString('ru-RU')}</strong>
            </span>
            <span className="online-chart-tooltip-metric online-chart-tooltip-avg">
              ср. {activePoint.avg.toLocaleString('ru-RU')}
            </span>
            {activePoint.peakAtLabel && (
              <span className="online-chart-tooltip-at">{activePoint.peakAtLabel}</span>
            )}
          </div>
        )}
      </div>

      {count >= 5 && (
        <div className="online-chart-minimap-wrap">
          <div
            className="online-chart-minimap"
            onPointerDown={onMinimapDown}
            onPointerMove={onMinimapMove}
            onPointerUp={onMinimapUp}
            onPointerCancel={onMinimapUp}
            role="presentation"
            aria-label="Мини-карта периода"
          >
            <svg viewBox={`0 0 ${CHART_W} ${MINI_H}`} preserveAspectRatio="none">
              {miniPeakPath && (
                <path d={miniPeakPath} fill="none" className="online-chart-minimap-line" strokeWidth="1.5" pointerEvents="none" />
              )}
              <rect
                x={(viewportLeftPct / 100) * CHART_W}
                y="4"
                width={Math.max(16, (viewportWidthPct / 100) * CHART_W)}
                height={MINI_H - 8}
                className="online-chart-minimap-window"
                rx="4"
                pointerEvents="none"
              />
            </svg>
          </div>
          <div className="online-chart-minimap-labels">
            <span>{points[0]?.shortLabel || points[0]?.label}</span>
            <span>{points[count - 1]?.shortLabel || points[count - 1]?.label}</span>
          </div>
        </div>
      )}

      <div className="online-chart-legend">
        <span className="online-chart-legend-item">
          <span className="online-chart-legend-line online-chart-legend-line-peak" />
          Пик
        </span>
        <span className="online-chart-legend-item">
          <span className="online-chart-legend-line online-chart-legend-line-avg" />
          Средний
        </span>
        <span className="online-chart-legend-item">
          <span className="panel-online-legend-dot panel-online-legend-dot-current" />
          Сейчас
        </span>
        <span className="online-chart-legend-item">
          <span className="panel-online-legend-dot panel-online-legend-dot-peak" />
          Макс. периода
        </span>
      </div>
    </div>
  )
}
