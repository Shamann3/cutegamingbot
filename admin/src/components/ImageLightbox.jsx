import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

function isCoarsePointer() {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(pointer: coarse)').matches
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
  const [zoomed, setZoomed] = useState(false)
  const start = useRef(null)

  useEffect(() => {
    setZoomed(false)
  }, [src])

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        e.stopPropagation()
        onClose()
      }
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

  if (!src) return null

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) onClose()
  }

  const onTouchStart = (e) => {
    const t = e.changedTouches?.[0]
    if (!t) return
    start.current = { x: t.clientX, y: t.clientY }
  }

  const onTouchEnd = (e) => {
    const t = e.changedTouches?.[0]
    const from = start.current
    start.current = null
    if (!t || !from) return
    const dx = t.clientX - from.x
    const dy = t.clientY - from.y
    if (Math.abs(dy) > 72 && Math.abs(dy) > Math.abs(dx) * 1.15) {
      onClose()
      return
    }
    if (Math.abs(dx) > 64 && Math.abs(dx) > Math.abs(dy)) {
      if (dx < 0 && onNext) onNext()
      if (dx > 0 && onPrev) onPrev()
    }
  }

  const coarse = isCoarsePointer()

  return createPortal(
    <div
      className="img-lightbox"
      onClick={handleBackdropClick}
      onTouchStart={onTouchStart}
      onTouchEnd={onTouchEnd}
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
      {onPrev ? (
        <button type="button" className="img-lightbox-nav is-prev" onClick={onPrev} aria-label="Предыдущее">
          ‹
        </button>
      ) : null}
      {onNext ? (
        <button type="button" className="img-lightbox-nav is-next" onClick={onNext} aria-label="Следующее">
          ›
        </button>
      ) : null}
      <div className="img-lightbox-stage" onClick={handleBackdropClick}>
        <img
          src={src}
          alt={alt}
          className={`img-lightbox-img${zoomed && !coarse ? ' img-lightbox-img-zoom' : ''}`}
          onClick={(e) => {
            e.stopPropagation()
            if (!coarse) setZoomed((z) => !z)
          }}
          draggable={false}
        />
      </div>
      <div className="img-lightbox-bar">
        <span>
          {caption || alt}
          {total > 1 ? ` · ${index + 1} / ${total}` : ''}
        </span>
        <button type="button" className="img-lightbox-done" onClick={onClose}>
          Закрыть
        </button>
      </div>
    </div>,
    document.body,
  )
}
