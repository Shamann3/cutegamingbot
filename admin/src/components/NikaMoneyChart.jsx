import { useEffect, useMemo, useRef, useState } from 'react'

const W = 720
const H = 248
const PAD = { top: 18, right: 12, bottom: 32, left: 12 }
const MIN_SPAN = 3

function fullFmt(n) {
  return new Intl.NumberFormat('ru-RU').format(Math.round(Number(n) || 0))
}

function signedFmt(n) {
  const v = Number(n) || 0
  if (v > 0) return `+${fullFmt(v)}`
  if (v < 0) return `−${fullFmt(Math.abs(v))}`
  return '0'
}

export function NikaSpark({ values = [], className = '' }) {
  const nums = (Array.isArray(values) ? values : []).map((v) => Number(v) || 0)
  if (nums.length < 2) return null
  const min = Math.min(...nums)
  const max = Math.max(...nums)
  const span = Math.max(1, max - min)
  const up = nums[nums.length - 1] >= nums[0]
  const d = nums.map((v, i) => {
    const x = (i / (nums.length - 1)) * 132
    const y = 26 - ((v - min) / span) * 24
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`
  }).join(' ')
  return (
    <svg
      className={`nika-spark${up ? ' is-up' : ' is-down'}${className ? ` ${className}` : ''}`}
      viewBox="0 0 132 28"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path d={d} fill="none" />
    </svg>
  )
}

function defaultSpan(len) {
  if (len <= 16) return len
  return 14
}

export default function NikaMoneyChart({ points = [], mode = 'flow' }) {
  const wrapRef = useRef(null)
  const hideTimer = useRef(null)
  const [active, setActive] = useState(null)
  const [tip, setTip] = useState(null)
  const [win, setWin] = useState({ start: 0, span: 0 })
  const items = Array.isArray(points) ? points : []

  useEffect(() => {
    const span = defaultSpan(items.length)
    setWin({ start: Math.max(0, items.length - span), span })
    setActive(null)
    setTip(null)
    if (hideTimer.current) {
      clearTimeout(hideTimer.current)
      hideTimer.current = null
    }
  }, [items.length])

  useEffect(() => () => {
    if (hideTimer.current) clearTimeout(hideTimer.current)
  }, [])

  const start = Math.max(0, Math.min(win.start, Math.max(0, items.length - 1)))
  const span = Math.max(MIN_SPAN, Math.min(items.length || MIN_SPAN, win.span || items.length))
  const from = Math.max(0, Math.min(start, Math.max(0, items.length - span)))
  const visible = items.slice(from, from + span)

  const metrics = useMemo(() => {
    const plusMax = Math.max(0, ...visible.map((p) => Number(p.plus) || 0))
    const minusMax = Math.max(0, ...visible.map((p) => Number(p.minus) || 0))
    const sysVals = visible.map((p) => p.system).filter((v) => v != null)
    return {
      flowMax: Math.max(1, plusMax, minusMax),
      sysMin: sysVals.length ? Math.min(...sysVals) : 0,
      sysMax: sysVals.length ? Math.max(...sysVals) : 1,
      hasSystem: sysVals.length > 1,
    }
  }, [visible])

  const idx = active == null ? visible.length - 1 : Math.max(0, Math.min(visible.length - 1, active))
  const selected = visible[idx] || items[items.length - 1]

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return undefined
    const onWheel = (event) => {
      event.preventDefault()
      const rect = el.getBoundingClientRect()
      const frac = (event.clientX - rect.left) / Math.max(1, rect.width)
      zoomAt(frac, event.deltaY > 0 ? 1.28 : 0.78)
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  })

  if (!items.length) {
    return (
      <div className="nika-chart nika-chart-empty">
        <p>Пока нет движений с запуска Ники. Плюсы и минусы появятся здесь сами.</p>
      </div>
    )
  }

  const innerW = W - PAD.left - PAD.right
  const midY = PAD.top + (H - PAD.top - PAD.bottom) * 0.58
  const upH = midY - PAD.top
  const downH = H - PAD.bottom - midY
  const gap = innerW / Math.max(1, visible.length)
  const barW = Math.max(4, Math.min(22, gap * 0.55))

  const sysPts = visible.map((p, i) => {
    if (p.system == null) return null
    const sysSpan = Math.max(1, metrics.sysMax - metrics.sysMin)
    const x = PAD.left + gap * i + gap / 2
    const y = PAD.top + (1 - (p.system - metrics.sysMin) / sysSpan) * (H - PAD.top - PAD.bottom)
    return { x, y }
  })
  const sysLine = sysPts.filter(Boolean)
  const sysPath = sysLine.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')

  const hideTip = () => {
    if (hideTimer.current) {
      clearTimeout(hideTimer.current)
      hideTimer.current = null
    }
    setTip(null)
  }

  const leaveBar = (event) => {
    if (event.pointerType === 'touch') return
    const cls = event.relatedTarget?.getAttribute?.('class') || ''
    if (cls.includes('nika-bar-plus') || cls.includes('nika-bar-minus')) return
    if (hideTimer.current) clearTimeout(hideTimer.current)
    hideTimer.current = setTimeout(() => setTip(null), 70)
  }

  const showBarTip = (i, side) => {
    if (hideTimer.current) {
      clearTimeout(hideTimer.current)
      hideTimer.current = null
    }
    const safe = Math.max(0, Math.min(visible.length - 1, i))
    const point = visible[safe]
    const el = wrapRef.current
    if (!point || !el) return
    setActive(safe)
    const r = el.getBoundingClientRect()
    const plusH = Number(point.plus) > 0 ? Math.max(10, (Number(point.plus) / metrics.flowMax) * upH) : 0
    const minusH = Number(point.minus) > 0 ? Math.max(10, (Number(point.minus) / metrics.flowMax) * downH) : 0
    const cx = PAD.left + gap * safe + gap / 2
    const y0 = side === 'plus' ? midY - plusH : midY
    const y1 = side === 'plus' ? midY : midY + minusH
    const sx = r.width / W
    const sy = r.height / H
    const boxW = 148
    const boxH = 72
    let left = (cx + barW / 2) * sx + 10
    let place = 'right'
    if (left + boxW > r.width - 8) {
      left = (cx - barW / 2) * sx - boxW - 10
      place = 'left'
    }
    if (left < 8) {
      left = 8
      place = 'right'
    }
    let top = ((y0 + y1) / 2) * sy - boxH / 2
    if (top < 8) top = 8
    if (top + boxH > r.height - 8) top = r.height - boxH - 8
    setTip({ i: safe, side, left, top, place })
  }

  const zoomAt = (frac, factor) => {
    const nextSpan = Math.max(MIN_SPAN, Math.min(items.length, Math.round(span * factor)))
    const center = from + span * frac
    let nextStart = Math.round(center - nextSpan / 2)
    nextStart = Math.max(0, Math.min(Math.max(0, items.length - nextSpan), nextStart))
    setWin({ start: nextStart, span: nextSpan })
  }

  const pan = (dir) => {
    const step = Math.max(1, Math.round(span * 0.35))
    setWin((cur) => {
      const next = Math.max(0, Math.min(Math.max(0, items.length - (cur.span || span)), (cur.start || 0) + dir * step))
      return { ...cur, start: next }
    })
  }

  const tickEvery = Math.max(1, Math.ceil(visible.length / (visible.length > 18 ? 6 : 5)))
  const zoomed = span < items.length
  const pointKind = String(selected?.t || '').includes('T') && selected?.label?.includes(':') ? 'час' : 'день'

  return (
    <div className="nika-chart">
      <div className="nika-chart-readout">
        <div>
          <span className="nika-plus">+{fullFmt(selected?.plus)}</span>
          <small>плюс Ники</small>
        </div>
        <div>
          <span className="nika-minus">−{fullFmt(selected?.minus)}</span>
          <small>минус Ники</small>
        </div>
        <div>
          <span className={(selected?.net || 0) >= 0 ? 'nika-plus' : 'nika-minus'}>
            {signedFmt(selected?.net)}
          </span>
          <small>итог Ники · {selected?.label}</small>
        </div>
      </div>
      {selected?.system != null && (
        <p className="nika-chart-sub">
          Все балансы в этот {pointKind}: {fullFmt(selected.system)}
          {selected.users != null ? ` · игроки ${fullFmt(selected.users)}` : ''}
          {selected.chats != null ? ` + чаты ${fullFmt(selected.chats)}` : ''}
          {selected.systemDelta != null ? ` · сдвиг ${signedFmt(selected.systemDelta)}` : ''}
        </p>
      )}

      <div className="nika-chart-zoom" role="group" aria-label="Масштаб графика">
        <button type="button" className="nika-chart-zoom-btn" disabled={span <= MIN_SPAN} onClick={() => zoomAt(0.5, 0.7)}>Ближе</button>
        <button type="button" className="nika-chart-zoom-btn" disabled={span >= items.length} onClick={() => zoomAt(0.5, 1.35)}>Дальше</button>
        <button type="button" className="nika-chart-zoom-btn" disabled={!zoomed} onClick={() => setWin({ start: 0, span: items.length })}>Все {items.length}</button>
        {zoomed ? (
          <>
            <button type="button" className="nika-chart-zoom-btn" disabled={from <= 0} onClick={() => pan(-1)}>←</button>
            <button type="button" className="nika-chart-zoom-btn" disabled={from + span >= items.length} onClick={() => pan(1)}>→</button>
          </>
        ) : null}
        <em>{visible[0]?.label} — {visible[visible.length - 1]?.label}</em>
      </div>

      <div
        ref={wrapRef}
        className="nika-chart-touch"
        onPointerDown={hideTip}
        onPointerLeave={hideTip}
        onKeyDown={(e) => {
          if (e.key === 'ArrowLeft') {
            e.preventDefault()
            setActive((cur) => Math.max(0, (cur == null ? visible.length - 1 : cur) - 1))
            hideTip()
          }
          if (e.key === 'ArrowRight') {
            e.preventDefault()
            setActive((cur) => Math.min(visible.length - 1, (cur == null ? visible.length - 1 : cur) + 1))
            hideTip()
          }
        }}
        role="img"
        tabIndex={0}
        aria-label="Плюсы и минусы. Подсказка только на зелёном или красном. Колесо — масштаб."
      >
        <svg
          className="nika-chart-svg"
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <line className="nika-chart-mid" x1={PAD.left} x2={W - PAD.right} y1={midY} y2={midY} />
          {sysPath && metrics.hasSystem ? <path className="nika-chart-sys" d={sysPath} fill="none" /> : null}
          {visible.map((p, i) => {
            const cx = PAD.left + gap * i + gap / 2
            const plusH = Number(p.plus) > 0 ? Math.max(10, ((Number(p.plus) || 0) / metrics.flowMax) * upH) : 0
            const minusH = Number(p.minus) > 0 ? Math.max(10, ((Number(p.minus) || 0) / metrics.flowMax) * downH) : 0
            const on = tip?.i === i
            return (
              <g key={p.t || i} className={`nika-bar${on ? ' is-on' : ''}`}>
                {plusH > 0 ? (
                  <rect
                    className="nika-bar-plus"
                    x={cx - barW / 2}
                    y={midY - plusH}
                    width={barW}
                    height={plusH}
                    rx={Math.min(7, barW / 2)}
                    style={{ transformOrigin: `${cx}px ${midY}px`, animationDelay: `${Math.min(i * 18, 420)}ms` }}
                    onPointerEnter={() => showBarTip(i, 'plus')}
                    onPointerDown={(e) => { e.stopPropagation(); showBarTip(i, 'plus') }}
                    onPointerLeave={leaveBar}
                  />
                ) : (
                  <circle className="nika-chart-dot is-flat" cx={cx} cy={midY} r={2.1} />
                )}
                {minusH > 0 ? (
                  <rect
                    className="nika-bar-minus"
                    x={cx - barW / 2}
                    y={midY}
                    width={barW}
                    height={minusH}
                    rx={Math.min(7, barW / 2)}
                    style={{ transformOrigin: `${cx}px ${midY}px`, animationDelay: `${Math.min(i * 18, 420)}ms` }}
                    onPointerEnter={() => showBarTip(i, 'minus')}
                    onPointerDown={(e) => { e.stopPropagation(); showBarTip(i, 'minus') }}
                    onPointerLeave={leaveBar}
                  />
                ) : null}
              </g>
            )
          })}
          {visible.map((p, i) => (
            (i === 0 || i === visible.length - 1 || i % tickEvery === 0) ? (
              <text key={`l${i}`} className="nika-chart-tick" x={PAD.left + gap * i + gap / 2} y={H - 8} textAnchor="middle">
                {p.label}
              </text>
            ) : null
          ))}
        </svg>
        {tip && visible[tip.i] && (
          <aside
            key={`${tip.i}-${tip.side}`}
            className={`nika-chart-tip is-${tip.side} is-${tip.place || 'right'}`}
            style={{ left: tip.left, top: tip.top }}
            role="status"
          >
            <span className="nika-chart-tip-kicker">{visible[tip.i].label}</span>
            {tip.side === 'plus' ? (
              <>
                <strong className="nika-plus">+{fullFmt(visible[tip.i].plus)}</strong>
                <small>копилка {fullFmt(visible[tip.i].plusVault)} · игры {fullFmt(visible[tip.i].commission)}</small>
              </>
            ) : (
              <>
                <strong className="nika-minus">−{fullFmt(visible[tip.i].minus)}</strong>
                <small>долив баланса групп</small>
              </>
            )}
          </aside>
        )}
      </div>
      <div className="nika-chart-legend">
        <span className="is-plus">вверх — плюс Ники</span>
        <span className="is-minus">вниз — минус Ники</span>
        {metrics.hasSystem ? <span className="is-sys">линия — все балансы в тот день</span> : null}
        <span>наведи на зелёное или красное</span>
      </div>
    </div>
  )
}

export { fullFmt as fmtShort, signedFmt }
