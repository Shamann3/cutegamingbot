import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

// Telegram-подобный просмотрщик изображений: клик по фото → оно
// разворачивается по центру экрана поверх затемнённого фона.
// Закрытие: клик по фону, Esc, кнопка ✕. Клик по фото — зум 1x ↔ 2x.
export default function ImageLightbox({ src, alt = 'фото', onClose }) {
  const [zoomed, setZoomed] = useState(false)
  const [closing, setClosing] = useState(false)
  const closeTimer = useRef(null)

  const handleClose = useCallback(() => {
    if (closing) return
    setClosing(true)
    closeTimer.current = setTimeout(onClose, 180)
  }, [closing, onClose])

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') handleClose() }
    window.addEventListener('keydown', onKey)
    // Блокируем прокрутку страницы под лайтбоксом
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
      clearTimeout(closeTimer.current)
    }
  }, [handleClose])

  if (!src) return null

  return createPortal(
    <div
      className={`img-lightbox${closing ? ' img-lightbox-closing' : ''}`}
      onClick={handleClose}
      role="dialog"
      aria-modal="true"
    >
      <button className="img-lightbox-close" onClick={handleClose} aria-label="Закрыть">✕</button>
      <a
        className="img-lightbox-download"
        href={src}
        download
        onClick={(e) => e.stopPropagation()}
        title="Скачать"
        aria-label="Скачать"
      >⤓</a>
      <img
        src={src}
        alt={alt}
        className={`img-lightbox-img${zoomed ? ' img-lightbox-img-zoom' : ''}`}
        onClick={(e) => { e.stopPropagation(); setZoomed((z) => !z) }}
        draggable={false}
      />
    </div>,
    document.body,
  )
}
