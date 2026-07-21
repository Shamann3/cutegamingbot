import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'

// Telegram-подобный просмотрщик изображений: клик по фото → оно
// разворачивается по центру экрана поверх затемнённого фона.
// Закрытие: клик по фону, Esc, кнопка ✕. Клик по фото — зум 1x ↔ 2x.
export default function ImageLightbox({ src, alt = 'фото', onClose }) {
  const [zoomed, setZoomed] = useState(false)

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        e.stopPropagation()
        onClose()
      }
    }
    // capture-фаза, чтобы никакой другой обработчик не перехватил Esc
    document.addEventListener('keydown', onKey, true)
    // Блокируем прокрутку страницы под лайтбоксом
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey, true)
      document.body.style.overflow = prevOverflow
    }
  }, [onClose])

  if (!src) return null

  // Закрываем только если клик пришёлся именно по фону, а не по фото/кнопкам
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) onClose()
  }

  return createPortal(
    <div
      className="img-lightbox"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
    >
      <button className="img-lightbox-close" onClick={onClose} aria-label="Закрыть">✕</button>
      <a
        className="img-lightbox-download"
        href={src}
        download
        onClick={(e) => e.stopPropagation()}
        title="Скачать"
        aria-label="Скачать"
      >⤓</a>
      <div className="img-lightbox-stage" onClick={handleBackdropClick}>
        <img
          src={src}
          alt={alt}
          className={`img-lightbox-img${zoomed ? ' img-lightbox-img-zoom' : ''}`}
          onClick={(e) => { e.stopPropagation(); setZoomed((z) => !z) }}
          draggable={false}
        />
      </div>
    </div>,
    document.body,
  )
}
