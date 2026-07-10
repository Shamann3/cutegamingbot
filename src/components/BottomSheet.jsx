import { useCallback, useEffect, useRef, useState } from 'react'
import { useEscapeClose } from '../hooks/useEscapeClose'
import Portal from './Portal'

const CLOSE_DRAG_PX = 90
const CLOSE_VELOCITY = 0.45
const CLOSE_ANIM_MS = 280
const DRAG_START_PX = 10
const OPTION_DRAG_START_RATIO = 0.5

function createDragState() {
  return {
    startY: 0,
    startX: 0,
    startTime: 0,
    active: false,
    dragging: false,
  }
}

function canStartSheetDrag(event) {
  const target = event.target
  if (!(target instanceof Element)) return false
  if (target.closest('.shop-sheet-apply')) return false

  const option = target.closest('.shop-sheet-option')
  if (option) {
    const rect = option.getBoundingClientRect()
    const relativeX = event.clientX - rect.left
    return relativeX >= rect.width * OPTION_DRAG_START_RATIO
  }

  return true
}

export default function BottomSheet({
  isOpen,
  onClose,
  title,
  children,
  onApply,
  applyLabel = 'Применить',
  showApply = true,
}) {
  const sheetRef = useRef(null)
  const dragStateRef = useRef(createDragState())

  const [dragY, setDragY] = useState(0)
  const [isDragging, setIsDragging] = useState(false)
  const [isSnapping, setIsSnapping] = useState(false)
  const [overlayOpacity, setOverlayOpacity] = useState(0.72)

  useEffect(() => {
    if (!isOpen) return
    setDragY(0)
    setIsDragging(false)
    setIsSnapping(false)
    setOverlayOpacity(0.72)
  }, [isOpen])

  const animateClose = useCallback(() => {
    const sheetHeight = sheetRef.current?.offsetHeight ?? 360
    setIsDragging(false)
    setIsSnapping(true)
    setDragY(sheetHeight)
    setOverlayOpacity(0)

    window.setTimeout(() => {
      onClose()
      setDragY(0)
      setIsSnapping(false)
      setOverlayOpacity(0.72)
    }, CLOSE_ANIM_MS)
  }, [onClose])

  useEscapeClose(isOpen, animateClose, { enabled: !isDragging })

  const handleOverlayClick = () => {
    if (isDragging) return
    animateClose()
  }

  const handlePointerDown = (event) => {
    if (isSnapping || !canStartSheetDrag(event)) return

    dragStateRef.current = {
      startY: event.clientY,
      startX: event.clientX,
      startTime: Date.now(),
      active: true,
      dragging: false,
    }
  }

  const beginDragging = (event) => {
    const state = dragStateRef.current
    if (state.dragging) return

    state.dragging = true
    setIsDragging(true)
    setIsSnapping(false)
    sheetRef.current?.setPointerCapture(event.pointerId)
  }

  const handlePointerMove = (event) => {
    const state = dragStateRef.current
    if (!state.active) return

    const deltaY = event.clientY - state.startY
    const deltaX = event.clientX - state.startX

    if (!state.dragging) {
      if (deltaY < DRAG_START_PX) return
      if (Math.abs(deltaX) > deltaY) return
      beginDragging(event)
    }

    const delta = Math.max(0, deltaY)
    const sheetHeight = sheetRef.current?.offsetHeight ?? 360
    const progress = Math.min(delta / sheetHeight, 1)

    setDragY(delta)
    setOverlayOpacity(0.72 * (1 - progress * 0.85))
  }

  const resetDragState = () => {
    dragStateRef.current = createDragState()
  }

  const handlePointerUp = (event) => {
    const state = dragStateRef.current
    if (!state.active) return

    if (!state.dragging) {
      resetDragState()
      return
    }

    const delta = Math.max(0, event.clientY - state.startY)
    const elapsed = Math.max(Date.now() - state.startTime, 16)
    const velocity = delta / elapsed
    resetDragState()
    setIsDragging(false)

    if (sheetRef.current?.hasPointerCapture(event.pointerId)) {
      sheetRef.current.releasePointerCapture(event.pointerId)
    }

    if (delta > CLOSE_DRAG_PX || velocity > CLOSE_VELOCITY) {
      animateClose()
      return
    }

    if (delta <= 0) return

    setIsSnapping(true)
    setDragY(0)
    setOverlayOpacity(0.72)
    window.setTimeout(() => setIsSnapping(false), CLOSE_ANIM_MS)
  }

  if (!isOpen) return null

  const sheetStyle = {
    transform: dragY > 0 || isSnapping ? `translateY(${dragY}px)` : undefined,
    transition: isDragging ? 'none' : isSnapping ? `transform ${CLOSE_ANIM_MS}ms cubic-bezier(0.32, 0.72, 0, 1)` : undefined,
  }

  return (
    <Portal lockScroll>
      <div
        className="shop-sheet-root"
        role="presentation"
        style={{ backgroundColor: `rgba(2, 6, 4, ${overlayOpacity})` }}
        onClick={handleOverlayClick}
      >
        <div
          ref={sheetRef}
          className={`shop-sheet ${dragY === 0 && !isSnapping ? 'shop-sheet-enter' : ''} ${isDragging ? 'shop-sheet-dragging' : ''}`}
          style={sheetStyle}
          role="dialog"
          aria-modal="true"
          aria-labelledby={title ? 'shop-sheet-title' : undefined}
          onClick={(event) => event.stopPropagation()}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
        >
          <div className="shop-sheet-drag-head">
            <div className="shop-sheet-handle" aria-hidden />
            {title ? (
              <h2 id="shop-sheet-title" className="shop-sheet-title farm-title-serif">
                {title}
              </h2>
            ) : null}
          </div>
          <div className="shop-sheet-body">{children}</div>
          {showApply ? (
            <button type="button" className="shop-sheet-apply farm-btn-primary" onClick={onApply ?? onClose}>
              {applyLabel}
            </button>
          ) : null}
        </div>
      </div>
    </Portal>
  )
}
