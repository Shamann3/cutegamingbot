import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

const MIN = 1
const MAX = 6

function clamp(n, a, b) {
  return Math.min(b, Math.max(a, n))
}

function touchDist(a, b) {
  return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY)
}

export default function ImageLightbox({
  src,
  alt = 'фото',
  onClose,
  onPrev,
  onNext,
  caption = '',
  index = 0,
  total = 0,
}) {
  const [scale, setScale] = useState(1)
  const [pos, setPos] = useState({ x: 0, y: 0 })
  const scaleRef = useRef(1)
  const posRef = useRef({ x: 0, y: 0 })
  const drag = useRef(null)
  const pinch = useRef(null)
  const lastTap = useRef(0)
  const stageRef = useRef(null)

  const applyScale = (next) => {
    const value = clamp(next, MIN, MAX)
    scaleRef.current = value
    setScale(value)
    if (value <= 1) {
      posRef.current = { x: 0, y: 0 }
      setPos({ x: 0, y: 0 })
    }
    return value
  }

  const applyPos = (next) => {
    posRef.current = next
    setPos(next)
  }

  useEffect(() => {
    applyScale(1)
  }, [src])

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        e.stopPropagation()
        onClose()
      }
      if (e.key === '+' || e.key === '=') {
        e.preventDefault()
        applyScale(scaleRef.current * 1.25)
      }
      if (e.key === '-' || e.key === '_') {
        e.preventDefault()
        applyScale(scaleRef.current / 1.25)
      }
      if (e.key === '0') {
        e.preventDefault()
        applyScale(1)
      }
      if (scaleRef.current > 1) return
      if (e.key === 'ArrowLeft' && onPrev) {
        e.preventDefault()
        onPrev()
      }
      if (e.key === 'ArrowRight' && onNext) {
        e.preventDefault()
        onNext()
      }
    }
    document.addEventListener('keydown', onKey, true)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey, true)
      document.body.style.overflow = prevOverflow
    }
  }, [onClose, onPrev, onNext])

  useEffect(() => {
    const node = stageRef.current
    if (!node) return undefined
    const onWheel = (e) => {
      e.preventDefault()
      const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12
      applyScale(scaleRef.current * factor)
    }
    node.addEventListener('wheel', onWheel, { passive: false })
    return () => node.removeEventListener('wheel', onWheel)
  }, [src])

  if (!src) return null

  const zoomed = scale > 1.02

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget && !zoomed) onClose()
  }

  const toggleZoom = () => {
    applyScale(scaleRef.current > 1.2 ? 1 : 2.4)
  }

  const onPointerDown = (e) => {
    if (e.pointerType === 'touch') return
    if (!zoomed) return
    e.currentTarget.setPointerCapture?.(e.pointerId)
    drag.current = {
      x: e.clientX,
      y: e.clientY,
      px: posRef.current.x,
      py: posRef.current.y,
    }
  }

  const onPointerMove = (e) => {
    const from = drag.current
    if (!from || e.pointerType === 'touch') return
    applyPos({
      x: from.px + (e.clientX - from.x),
      y: from.py + (e.clientY - from.y),
    })
  }

  const onPointerUp = (e) => {
    if (e.pointerType === 'touch') return
    const from = drag.current
    drag.current = null
    if (!from) return
    const moved = Math.hypot(e.clientX - from.x, e.clientY - from.y)
    if (moved < 8 && e.detail === 2) toggleZoom()
  }

  const onDoubleClick = (e) => {
    e.preventDefault()
    toggleZoom()
  }

  const onTouchStart = (e) => {
    if (e.touches.length >= 2) {
      pinch.current = {
        dist: touchDist(e.touches[0], e.touches[1]),
        scale: scaleRef.current,
      }
      drag.current = null
      return
    }
    const t = e.touches[0]
    if (!t) return
    drag.current = {
      x: t.clientX,
      y: t.clientY,
      px: posRef.current.x,
      py: posRef.current.y,
      at: Date.now(),
    }
  }

  const onTouchMove = (e) => {
    if (e.touches.length >= 2 && pinch.current) {
      e.preventDefault()
      const next = pinch.current.scale * (touchDist(e.touches[0], e.touches[1]) / pinch.current.dist)
      applyScale(next)
      return
    }
    const from = drag.current
    const t = e.touches[0]
    if (!from || !t || scaleRef.current <= 1) return
    e.preventDefault()
    applyPos({
      x: from.px + (t.clientX - from.x),
      y: from.py + (t.clientY - from.y),
    })
  }

  const onTouchEnd = (e) => {
    if (e.touches.length >= 2) return
    if (e.touches.length === 1) {
      pinch.current = null
      return
    }
    const from = drag.current
    const pinching = Boolean(pinch.current)
    pinch.current = null
    drag.current = null
    const t = e.changedTouches?.[0]
    if (!t || !from || pinching) return
    const dx = t.clientX - from.x
    const dy = t.clientY - from.y
    const moved = Math.hypot(dx, dy)
    if (scaleRef.current > 1) return
    if (moved < 18) {
      const now = Date.now()
      if (now - lastTap.current < 280) {
        toggleZoom()
        lastTap.current = 0
        return
      }
      lastTap.current = now
      return
    }
    if (Math.abs(dy) > 72 && Math.abs(dy) > Math.abs(dx) * 1.15) {
      onClose()
      return
    }
    if (Math.abs(dx) > 64 && Math.abs(dx) > Math.abs(dy)) {
      if (dx < 0 && onNext) onNext()
      if (dx > 0 && onPrev) onPrev()
    }
  }

  return createPortal(
    <div
      className="img-lightbox"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-label="Просмотр фото"
    >
      <button type="button" className="img-lightbox-close" onClick={onClose} aria-label="Закрыть">
        ✕
      </button>
      <a
        className="img-lightbox-download"
        href={src}
        download
        onClick={(e) => e.stopPropagation()}
        title="Скачать"
        aria-label="Скачать"
      >
        ⤓
      </a>
      {onPrev && !zoomed ? (
        <button type="button" className="img-lightbox-nav is-prev" onClick={onPrev} aria-label="Предыдущее">
          ‹
        </button>
      ) : null}
      {onNext && !zoomed ? (
        <button type="button" className="img-lightbox-nav is-next" onClick={onNext} aria-label="Следующее">
          ›
        </button>
      ) : null}
      <div
        ref={stageRef}
        className={`img-lightbox-stage${zoomed ? ' is-zoomed' : ''}`}
        onClick={handleBackdropClick}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
      >
        <img
          src={src}
          alt={alt}
          className={`img-lightbox-img${zoomed ? ' img-lightbox-img-zoom' : ''}`}
          style={{ transform: `translate(${pos.x}px, ${pos.y}px) scale(${scale})` }}
          onClick={(e) => e.stopPropagation()}
          onDoubleClick={onDoubleClick}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={() => { drag.current = null }}
          draggable={false}
        />
      </div>
      <div className="img-lightbox-bar">
        <span>
          {caption || alt}
          {total > 1 ? ` · ${index + 1} / ${total}` : ''}
          {' · щипок или колесо'}
        </span>
        <div className="img-lightbox-zoom">
          <button type="button" onClick={() => applyScale(scaleRef.current / 1.25)} aria-label="Отдалить">−</button>
          <button type="button" onClick={() => applyScale(1)} aria-label="Сбросить">1×</button>
          <button type="button" onClick={() => applyScale(scaleRef.current * 1.25)} aria-label="Приблизить">+</button>
        </div>
        <button type="button" className="img-lightbox-done" onClick={onClose}>
          Закрыть
        </button>
      </div>
    </div>,
    document.body,
  )
}
