let lockCount = 0
let snapshot = null

function applyScrollLock() {
  const root = document.getElementById('root')
  if (!root) return

  snapshot = {
    rootOverflow: root.style.overflow,
    rootTouchAction: root.style.touchAction,
  }

  root.style.overflow = 'hidden'
  root.style.touchAction = 'none'
}

function restoreScrollLock() {
  if (!snapshot) return

  const root = document.getElementById('root')
  if (root) {
    root.style.overflow = snapshot.rootOverflow
    root.style.touchAction = snapshot.rootTouchAction
  }

  snapshot = null
}

export function acquireScrollLock() {
  if (lockCount === 0) {
    applyScrollLock()
  }
  lockCount += 1
}

export function releaseScrollLock() {
  if (lockCount <= 0) return
  lockCount -= 1
  if (lockCount === 0) {
    restoreScrollLock()
  }
}
