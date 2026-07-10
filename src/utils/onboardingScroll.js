const SCROLL_RETRY_MS = 120
const SCROLL_MAX_ATTEMPTS = 12
const SCROLL_SETTLE_MS = 140
const SCROLL_FALLBACK_MS = 1600

export function findOnboardingPlot(plotId) {
  return document.querySelector(`[data-onboarding-plot="${String(plotId)}"]`)
}

export function findOnboardingBackpack() {
  const section = document.getElementById('onboarding-backpack')
  if (!section) return null
  return section.closest('.inventory-board-frame') ?? section.closest('.farm-vine-frame') ?? section
}

function easeInOutQuad(t) {
  return t < 0.5 ? 2 * t * t : 1 - ((-2 * t + 2) ** 2) / 2
}

function tabBarClearancePx() {
  const tab = document.querySelector('.app-tab-bar')
  return (tab?.getBoundingClientRect().height ?? 80) + 20
}

function scrollTargetY(node, block = 'end') {
  const rect = node.getBoundingClientRect()
  const nodeTop = rect.top + window.scrollY
  const tabBarOffset = 88

  if (block === 'end') {
    return Math.max(0, nodeTop - window.innerHeight + rect.height + tabBarOffset)
  }
  if (block === 'center') {
    return Math.max(0, nodeTop - (window.innerHeight - rect.height) / 2)
  }
  return Math.max(0, nodeTop)
}

function scrollTargetYForPlot(node) {
  const rect = node.getBoundingClientRect()
  const docTop = rect.top + window.scrollY
  const docBottom = rect.bottom + window.scrollY
  const clearance = tabBarClearancePx()
  const topPadding = 8
  const targetBottomInViewport = window.innerHeight - clearance

  let targetY = docBottom - targetBottomInViewport
  if (docTop - targetY < topPadding) {
    targetY = docTop - topPadding
  }

  return Math.max(0, targetY)
}

function animateScrollTo(node, { block = 'end', durationMs = 1400 } = {}) {
  const targetY = scrollTargetY(node, block)
  return animateScrollToY(targetY, { durationMs })
}

function animateScrollToY(targetY, { durationMs = 1400 } = {}) {
  const startY = window.scrollY
  const distance = targetY - startY

  if (Math.abs(distance) < 4) return Promise.resolve(true)

  return new Promise((resolve) => {
    const startTime = performance.now()

    const tick = (now) => {
      const progress = Math.min(1, (now - startTime) / durationMs)
      window.scrollTo(0, startY + distance * easeInOutQuad(progress))
      if (progress < 1) {
        requestAnimationFrame(tick)
      } else {
        resolve(true)
      }
    }

    requestAnimationFrame(tick)
  })
}

function measureBalanceViewportBounds(node) {
  const chips = node.querySelectorAll('.farm-stat-bar')
  if (!chips.length) {
    const rect = node.getBoundingClientRect()
    return {
      top: rect.top + window.scrollY,
      bottom: rect.bottom + window.scrollY,
    }
  }

  let minTop = Infinity
  let maxBottom = -Infinity

  chips.forEach((chip) => {
    const box = chip.getBoundingClientRect()
    minTop = Math.min(minTop, box.top)
    maxBottom = Math.max(maxBottom, box.bottom)
  })

  return {
    top: minTop + window.scrollY,
    bottom: maxBottom + window.scrollY,
  }
}

function balanceScrollTargetY(node) {
  const bounds = measureBalanceViewportBounds(node)
  const card = document.querySelector('.onboarding-card-float')
  const cardHeight = card?.getBoundingClientRect().height ?? 0
  const tabBarOffset = 88
  const gap = 18
  const bottomReserve = Math.max(260, cardHeight + tabBarOffset + gap)
  const topPadding = 6

  const targetBottomInViewport = window.innerHeight - bottomReserve
  let targetY = bounds.bottom - targetBottomInViewport

  const maxYForTop = bounds.top - topPadding
  if (bounds.top - targetY < topPadding) {
    targetY = maxYForTop
  }

  return Math.max(0, targetY)
}

function unlockBodyScroll() {
  const prevOverflow = document.body.style.overflow
  if (prevOverflow === 'hidden') {
    document.body.style.overflow = ''
  }
  return prevOverflow
}

function restoreBodyScroll(prevOverflow) {
  if (prevOverflow === 'hidden') {
    window.setTimeout(() => {
      document.body.style.overflow = 'hidden'
    }, 120)
  }
}

function waitForSmoothScrollEnd() {
  return new Promise((resolve) => {
    let settled = false
    let settleTimer = null

    const finish = () => {
      if (settled) return
      settled = true
      window.removeEventListener('scroll', onScroll, true)
      window.clearTimeout(settleTimer)
      window.clearTimeout(fallbackTimer)
      resolve(true)
    }

    const onScroll = () => {
      window.clearTimeout(settleTimer)
      settleTimer = window.setTimeout(finish, SCROLL_SETTLE_MS)
    }

    const fallbackTimer = window.setTimeout(finish, SCROLL_FALLBACK_MS)
    window.addEventListener('scroll', onScroll, true)
    onScroll()
  })
}

export function smoothScrollToElement(node, { block = 'center' } = {}) {
  if (!node) return Promise.resolve(false)
  node.scrollIntoView({ behavior: 'smooth', block, inline: 'nearest' })
  return waitForSmoothScrollEnd()
}

export function findOnboardingBalance() {
  return document.querySelector('#onboarding-balance')
}

export function smoothScrollToBackpack({ durationMs = 1800, block = 'center' } = {}) {
  const node = findOnboardingBackpack()
  if (!node) return Promise.resolve(false)

  const prevOverflow = unlockBodyScroll()

  return animateScrollTo(node, { block, durationMs }).then((result) => {
    restoreBodyScroll(prevOverflow)
    return result
  })
}

export function playBackpackRevealAnimation(durationMs = 900) {
  const frame = findOnboardingBackpack()
  if (!frame) return Promise.resolve(false)

  frame.classList.remove('inventory-board-frame--reveal')
  void frame.offsetWidth
  frame.classList.add('inventory-board-frame--reveal')

  return new Promise((resolve) => {
    window.setTimeout(() => resolve(true), durationMs)
  })
}

export function clearBackpackRevealAnimation() {
  const frame = findOnboardingBackpack()
  frame?.classList.remove('inventory-board-frame--reveal')
}

export function smoothScrollToBalance({ durationMs = 1500 } = {}) {
  const node = findOnboardingBalance()
  if (!node) return Promise.resolve(false)

  const prevOverflow = unlockBodyScroll()

  const run = () => {
    const targetY = balanceScrollTargetY(node)
    return animateScrollToY(targetY, { durationMs }).then((result) => {
      restoreBodyScroll(prevOverflow)
      return result
    })
  }

  return new Promise((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        run().then(resolve)
      })
    })
  })
}

export async function smoothScrollToOnboardingPlot(plotId, { requireAction = null, slow = false } = {}) {
  const node = findOnboardingPlot(plotId)
  if (!node) return false

  if (requireAction) {
    const selector =
      requireAction === 'water'
        ? '.farm-btn-water'
        : requireAction === 'harvest'
          ? '.farm-btn-harvest'
          : null
    if (selector && !node.querySelector(selector)) return false
  }

  const prevOverflow = unlockBodyScroll()

  if (slow) {
    await animateScrollToY(scrollTargetYForPlot(node), { durationMs: 1500 })
  } else {
    await animateScrollToY(scrollTargetYForPlot(node), { durationMs: 900 })
  }

  restoreBodyScroll(prevOverflow)
  return true
}

export function scheduleOnboardingPlotScroll(plotId, options = {}) {
  let cancelled = false
  let attempts = 0
  let timerId = null

  const run = async () => {
    if (cancelled) return

    const scrolled = await smoothScrollToOnboardingPlot(plotId, options)
    if (scrolled || attempts >= SCROLL_MAX_ATTEMPTS) return

    attempts += 1
    timerId = window.setTimeout(run, SCROLL_RETRY_MS)
  }

  timerId = window.setTimeout(() => {
    run()
  }, options.slow ? 320 : 80)

  return () => {
    cancelled = true
    if (timerId) window.clearTimeout(timerId)
  }
}
