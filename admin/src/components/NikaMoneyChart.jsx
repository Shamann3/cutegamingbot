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
  const [active, setActive] = useState(null)
  const [tip, setTip] = useState(null)
  const [win, setWin] = useState({ start: 0, span: 0 })
  const items = Array.isArray(points) ? points : []

  useEffect(() => {
    const span = defaultSpan(items.length)
    setWin({ start: Math.max(0, items.length - span), span })
    setActive(null)
    setTip(null)
  }, [items.length])

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

  const setIndex = (next, clientX, clientY) => {
    const safe = Math.max(0, Math.min(visible.length - 1, next))
    setActive(safe)
    const el = wrapRef.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const x = clientX == null ? ((safe + 0.5) / visible.length) * r.width : clientX - r.left
    const y = clientY == null ? 24 : clientY - r.top
    setTip({
      i: safe,
      left: Math.max(8, Math.min(r.width - 220, x - 110)),
      top: Math.max(8, Math.min(r.height - 8, y - 12)),
    })
  }

  const scrub = (clientX, clientY) => {
    if (!visible.length) return
    const el = wrapRef.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const x = (clientX - r.left) / Math.max(1, r.width)
    setIndex(Math.floor(x * visible.length), clientX, clientY)
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
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId)
          scrub(e.clientX, e.clientY)
        }}
        onPointerMove={(e) => scrub(e.clientX, e.clientY)}
        onPointerLeave={() => setTip(null)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowLeft') {
            e.preventDefault()
            setIndex((active == null ? visible.length - 1 : active) - 1)
          }
          if (e.key === 'ArrowRight') {
            e.preventDefault()
            setIndex((active == null ? visible.length - 1 : active) + 1)
          }
        }}
        role="slider"
        tabIndex={0}
        aria-valuemin={0}
        aria-valuemax={Math.max(0, visible.length - 1)}
        aria-valuenow={idx}
        aria-label="Плюсы и минусы. Наведи — подробности. Колесо — масштаб."
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
                    style={{ transformOrigin: `${cx}px ${midY}px`, animationDelay: `${Math.min(i * 18, 420)}ms` }}
                  />
                ) : (
                  <circle className="nika-chart-dot is-flat" cx={cx} cy={midY} r={on ? 3.2 : 2.1} />
                )}
                {minusH > 0 ? (
                  <rect
                    className="nika-bar-minus"
                    x={cx - barW / 2}
                    y={midY}
                    width={barW}
                    height={minusH}
                    rx={Math.min(6, barW / 2)}
                    style={{ transformOrigin: `${cx}px ${midY}px`, animationDelay: `${Math.min(i * 18, 420)}ms` }}
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
          {visible.map((p, i) => (
            (i === 0 || i === visible.length - 1 || i % tickEvery === 0) ? (
              <text key={`l${i}`} className="nika-chart-tick" x={PAD.left + gap * i + gap / 2} y={H - 8} textAnchor="middle">
                {p.label}
              </text>
            ) : null
          ))}
        </svg>
        {tip && visible[tip.i] && (
          <aside className="nika-chart-tip" style={{ left: tip.left, top: 8 }} role="status">
            <b>{visible[tip.i].label}</b>
            <p>Плюс Ники <em className="nika-plus">+{fullFmt(visible[tip.i].plus)}</em></p>
            <small>
              копилка {fullFmt(visible[tip.i].plusVault)} · игры {fullFmt(visible[tip.i].commission)}
            </small>
            <p>Минус Ники <em className="nika-minus">−{fullFmt(visible[tip.i].minus)}</em></p>
            <small>долив баланса групп</small>
            <p>Итог Ники <em className={(visible[tip.i].net || 0) >= 0 ? 'nika-plus' : 'nika-minus'}>{signedFmt(visible[tip.i].net)}</em></p>
            {visible[tip.i].system != null ? (
              <>
                <p>Все балансы <em>{fullFmt(visible[tip.i].system)}</em></p>
                <small>
                  игроки {fullFmt(visible[tip.i].users)} + чаты {fullFmt(visible[tip.i].chats)}
                  {visible[tip.i].systemDelta != null ? ` · сдвиг ${signedFmt(visible[tip.i].systemDelta)}` : ''}
                </small>
              </>
            ) : (
              <small>Срез всех балансов за этот {pointKind} ещё не записан</small>
            )}
          </aside>
        )}
      </div>
      <div className="nika-chart-legend">
        <span className="is-plus">вверх — плюс Ники</span>
        <span className="is-minus">вниз — минус Ники</span>
        {metrics.hasSystem ? <span className="is-sys">линия — все балансы в тот день</span> : null}
        <span>наведи на точку · колесо ближе/дальше</span>
      </div>
    </div>
  )
}

export { fullFmt as fmtShort, signedFmt }
