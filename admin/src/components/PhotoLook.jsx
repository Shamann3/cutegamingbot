import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import TgPhoto, { loadTgPhotoUrl } from './TgPhoto'

const MIN = 1
const MAX = 4

function clamp(value) {
  const next = Math.round(Number(value) * 100) / 100
  return Math.min(MAX, Math.max(MIN, next))
}

function pairDistance(points) {
  const list = [...points.values()]
  if (list.length < 2) return 0
  return Math.hypot(list[0].x - list[1].x, list[0].y - list[1].y)
}

export default function PhotoLook({
  fileId,
  alt = 'Фото доказательства',
  eager = false,
  className = '',
}) {
  const [open, setOpen] = useState(false)
  const [scale, setScale] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [src, setSrc] = useState('')
  const [miss, setMiss] = useState(false)
  const stageRef = useRef(null)
  const pointers = useRef(new Map())
  const gesture = useRef(null)

  useEffect(() => {
    if (scale <= 1) setPan({ x: 0, y: 0 })
  }, [scale])

  useEffect(() => {
    if (!open) return undefined
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKey = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        event.stopPropagation()
        setOpen(false)
        return
      }
      if (event.key === '+' || event.key === '=') {
        event.preventDefault()
        event.stopPropagation()
        setScale((value) => clamp(value + 0.25))
        return
      }
      if (event.key === '-' || event.key === '_') {
        event.preventDefault()
        event.stopPropagation()
        setScale((value) => clamp(value - 0.25))
        return
      }
      if (event.key === '0') {
        event.preventDefault()
        event.stopPropagation()
        setScale(1)
        return
      }
      if (event.key.startsWith('Arrow')) event.stopPropagation()
    }
    window.addEventListener('keydown', onKey, true)
    return () => {
      document.body.style.overflow = previous
      window.removeEventListener('keydown', onKey, true)
    }
  }, [open])

  useEffect(() => {
    const stage = stageRef.current
    if (!open || !stage) return undefined
    const onWheel = (event) => {
      event.preventDefault()
      const step = event.deltaY < 0 ? 0.2 : -0.2
      setScale((value) => clamp(value + step))
    }
    stage.addEventListener('wheel', onWheel, { passive: false })
    return () => stage.removeEventListener('wheel', onWheel)
  }, [open])

  const close = () => setOpen(false)

  const openLook = async () => {
    setScale(1)
    setPan({ x: 0, y: 0 })
    setMiss(false)
    setOpen(true)
    try {
      const url = await loadTgPhotoUrl(fileId, 'full')
      setSrc(url || '')
      setMiss(!url)
    } catch {
      setSrc('')
      setMiss(true)
    }
  }

  const onPointerDown = (event) => {
    const stage = stageRef.current
    if (!stage) return
    stage.setPointerCapture?.(event.pointerId)
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY })
    if (pointers.current.size >= 2) {
      gesture.current = { kind: 'pinch', dist: pairDistance(pointers.current), scale }
      return
    }
    if (scale > 1) {
      gesture.current = { kind: 'pan', x: event.clientX, y: event.clientY, pan: { ...pan } }
    }
  }

  const onPointerMove = (event) => {
    if (!pointers.current.has(event.pointerId)) return
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY })
    const current = gesture.current
    if (!current) return
    if (current.kind === 'pinch' && pointers.current.size >= 2 && current.dist > 0) {
      const dist = pairDistance(pointers.current)
      setScale(clamp(current.scale * (dist / current.dist)))
      return
    }
    if (current.kind === 'pan') {
      setPan({
        x: current.pan.x + (event.clientX - current.x),
        y: current.pan.y + (event.clientY - current.y),
      })
    }
  }

  const onPointerUp = (event) => {
    pointers.current.delete(event.pointerId)
    if (pointers.current.size < 2 && gesture.current?.kind === 'pinch') gesture.current = null
    if (pointers.current.size === 0) gesture.current = null
  }

  const frameStyle = {
    width: '100%',
    height: 'auto',
    maxHeight: 'var(--look-max, min(78vh, 52rem))',
    objectFit: 'contain',
    borderRadius: 'var(--look-radius, 16px)',
    cursor: 'zoom-in',
  }

  const look = open ? (
    <div className="photo-look" role="dialog" aria-modal="true" aria-label={alt}>
      <div
        ref={stageRef}
        className="photo-look-stage"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onClick={(event) => {
          if (event.target === stageRef.current && scale <= 1) close()
        }}
      >
        {src ? (
          <img
            src={src}
            alt={alt}
            draggable={false}
            style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})` }}
          />
        ) : (
          <p className="photo-look-miss">{miss ? 'Фото не открылось. Закройте и нажмите ещё раз.' : 'Открываем фото…'}</p>
        )}
      </div>
      <div className="photo-look-bar">
        <button type="button" onClick={() => setScale((value) => clamp(value - 0.25))}>Дальше</button>
        <button type="button" onClick={() => { setScale(1) }}>Весь кадр</button>
        <button type="button" onClick={() => setScale((value) => clamp(value + 0.25))}>Ближе</button>
        <span className="photo-look-pct">{Math.round(scale * 100)}%</span>
        <button type="button" onClick={close}>Закрыть</button>
      </div>
    </div>
  ) : null

  return (
    <div className={`photo-look-slot${className ? ` ${className}` : ''}`}>
      <div
        className="photo-look-hit"
        role="button"
        tabIndex={0}
        aria-label="Открыть фото целиком"
        onClick={openLook}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            openLook()
          }
        }}
      >
        <TgPhoto
          fileId={fileId}
          lazy={!eager}
          alt={alt}
          className="photo-look-frame"
          style={frameStyle}
        />
        <span className="photo-look-open">Открыть фото</span>
      </div>
      {look && typeof document !== 'undefined' ? createPortal(look, document.body) : look}
    </div>
  )
}
