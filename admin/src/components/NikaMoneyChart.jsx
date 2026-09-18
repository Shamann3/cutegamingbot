import { useMemo, useRef, useState } from 'react'

const W = 720
const H = 248
const PAD = { top: 16, right: 10, bottom: 30, left: 10 }

function fmt(n) {
  const v = Math.round(Number(n) || 0)
  const abs = Math.abs(v)
  if (abs >= 1_000_000) return `${(v / 1_000_000).toFixed(abs >= 10_000_000 ? 0 : 1)} млн`
  if (abs >= 1000) return `${(v / 1000).toFixed(abs >= 10_000 ? 0 : 1)} тыс`
  return v.toLocaleString('ru-RU')
}

function signedFmt(n) {
  const v = Number(n) || 0
  if (v > 0) return `+${fmt(v)}`
  if (v < 0) return `−${fmt(Math.abs(v))}`
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

export default function NikaMoneyChart({ points = [], mode = 'flow' }) {
  const wrapRef = useRef(null)
  const [active, setActive] = useState(null)
  const items = Array.isArray(points) ? points : []

  const metrics = useMemo(() => {
    const plusMax = Math.max(0, ...items.map((p) => Number(p.plus) || 0))
    const minusMax = Math.max(0, ...items.map((p) => Number(p.minus) || 0))
    const sysVals = items.map((p) => p.system).filter((v) => v != null)
    const sysMin = sysVals.length ? Math.min(...sysVals) : 0
    const sysMax = sysVals.length ? Math.max(...sysVals) : 1
    return {
      plusMax,
      minusMax,
      flowMax: Math.max(1, plusMax, minusMax),
      sysMin,
      sysMax,
      hasSystem: sysVals.length > 1,
    }
  }, [items])

  if (!items.length) {
    return (
      <div className="nika-chart nika-chart-empty">
        <p>Пока нет движений с запуска Ники. Плюсы и минусы появятся здесь сами.</p>
      </div>
    )
  }

  const innerW = W - PAD.left - PAD.right
  const midY = PAD.top + (H - PAD.top - PAD.bottom) * 0.55
  const upH = midY - PAD.top
  const downH = H - PAD.bottom - midY
  const gap = innerW / items.length
  const barW = Math.max(3.5, Math.min(20, gap * 0.52))
  const idx = active == null ? items.length - 1 : active
  const selected = items[idx] || items[items.length - 1]

  const sysPts = items.map((p, i) => {
    if (p.system == null) return null
    const span = Math.max(1, metrics.sysMax - metrics.sysMin)
    const x = PAD.left + gap * i + gap / 2
    const y = PAD.top + (1 - (p.system - metrics.sysMin) / span) * (H - PAD.top - PAD.bottom)
    return { x, y }
  })
  const sysLine = sysPts.filter(Boolean)
  const sysPath = sysLine.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')
  const sysArea = sysLine.length > 1
    ? `${sysPath} L${sysLine[sysLine.length - 1].x.toFixed(1)} ${midY} L${sysLine[0].x.toFixed(1)} ${midY} Z`
    : ''

  const scrub = (clientX) => {
    const el = wrapRef.current
    if (!el || !items.length) return
    const r = el.getBoundingClientRect()
    const x = (clientX - r.left) / Math.max(1, r.width)
    const next = Math.max(0, Math.min(items.length - 1, Math.floor(x * items.length)))
    setActive(next)
  }

  const tickEvery = Math.max(1, Math.ceil(items.length / (items.length > 24 ? 6 : 5)))

  return (
    <div className="nika-chart">
      <div className="nika-chart-readout">
        <div>
          <span className="nika-plus">+{fmt(selected?.plus)}</span>
          <small>плюс</small>
        </div>
        <div>
          <span className="nika-minus">−{fmt(selected?.minus)}</span>
          <small>минус</small>
        </div>
        <div>
          <span className={(selected?.net || 0) >= 0 ? 'nika-plus' : 'nika-minus'}>
            {signedFmt(selected?.net)}
          </span>
          <small>{selected?.label || 'сальдо'}</small>
        </div>
        {selected?.systemDelta != null ? (
          <div>
            <span className={selected.systemDelta >= 0 ? 'nika-plus' : 'nika-minus'}>
              {signedFmt(selected.systemDelta)}
            </span>
            <small>все балансы</small>
          </div>
        ) : selected?.system != null ? (
          <div>
            <span>{fmt(selected.system)}</span>
            <small>система</small>
          </div>
        ) : null}
      </div>
      <div
        ref={wrapRef}
        className="nika-chart-touch"
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId)
          scrub(e.clientX)
        }}
        onPointerMove={(e) => scrub(e.clientX)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowLeft') {
            e.preventDefault()
            setActive((cur) => Math.max(0, (cur == null ? items.length - 1 : cur) - 1))
          }
          if (e.key === 'ArrowRight') {
            e.preventDefault()
            setActive((cur) => Math.min(items.length - 1, (cur == null ? items.length - 1 : cur) + 1))
          }
        }}
        role="slider"
        tabIndex={0}
        aria-valuemin={0}
        aria-valuemax={items.length - 1}
        aria-valuenow={idx}
        aria-label="Плюсы и минусы по времени. Стрелки листают, палец выбирает столбик."
      >
        <svg
          className="nika-chart-svg"
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <defs>
            <linearGradient id="nikaSysFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgba(255,255,255,0.22)" />
              <stop offset="100%" stopColor="rgba(255,255,255,0)" />
            </linearGradient>
          </defs>
          <line className="nika-chart-mid" x1={PAD.left} x2={W - PAD.right} y1={midY} y2={midY} />
          {sysArea && metrics.hasSystem ? <path className="nika-chart-sys-fill" d={sysArea} /> : null}
          {sysPath && metrics.hasSystem ? <path className="nika-chart-sys" d={sysPath} fill="none" /> : null}
          {items.map((p, i) => {
            const cx = PAD.left + gap * i + gap / 2
            const plusH = ((Number(p.plus) || 0) / metrics.flowMax) * upH
            const minusH = ((Number(p.minus) || 0) / metrics.flowMax) * downH
            const on = i === idx
            return (
              <g key={p.t || i} className={`nika-bar${on ? ' is-on' : ''}`}>
                {plusH > 0 ? (
                  <rect
                    className="nika-bar-plus"
                    x={cx - barW / 2}
                    y={midY - plusH}
                    width={barW}
                    height={plusH}
                    rx={Math.min(6, barW / 2)}
                    style={{
                      transformOrigin: `${cx}px ${midY}px`,
                      animationDelay: `${Math.min(i * 18, 420)}ms`,
                    }}
                  />
                ) : null}
                {minusH > 0 ? (
                  <rect
                    className="nika-bar-minus"
                    x={cx - barW / 2}
                    y={midY}
                    width={barW}
                    height={minusH}
                    rx={Math.min(6, barW / 2)}
                    style={{
                      transformOrigin: `${cx}px ${midY}px`,
                      animationDelay: `${Math.min(i * 18, 420)}ms`,
                    }}
                  />
                ) : null}
              </g>
            )
          })}
          <line
            className="nika-chart-hair"
            x1={PAD.left + gap * idx + gap / 2}
            x2={PAD.left + gap * idx + gap / 2}
            y1={PAD.top}
            y2={H - PAD.bottom}
          />
          {items.map((p, i) => (
            (i === 0 || i === items.length - 1 || i % tickEvery === 0) ? (
              <text
                key={`l${i}`}
                className="nika-chart-tick"
                x={PAD.left + gap * i + gap / 2}
                y={H - 8}
                textAnchor="middle"
              >
                {p.label}
              </text>
            ) : null
          ))}
        </svg>
      </div>
      <div className="nika-chart-legend">
        <span className="is-plus">плюс — копилка и комиссии</span>
        <span className="is-minus">минус — долив столов</span>
        {metrics.hasSystem ? <span className="is-sys">линия — все балансы</span> : null}
      </div>
    </div>
  )
}

export { fmt as fmtShort, signedFmt }
