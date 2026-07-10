import { useCallback, useLayoutEffect, useRef, useState } from 'react'

const DEFAULT_PADDING = 10
const DEFAULT_RADIUS = 14
const TRACE_STROKE = 2.5

const SPOTLIGHT_CONFIG = {
  balance: {
    padding: 5,
    radius: 12,
    ringClass: 'onboarding-spotlight-ring--balance',
  },
  'plot-1': { padding: 6, radius: 16, ringClass: 'onboarding-spotlight-ring--balance' },
  backpack: {
    padding: 6,
    radius: 14,
    ringClass: 'onboarding-spotlight-ring--balance',
  },
  'tab-shop': { padding: 4, radius: 13, ringClass: 'onboarding-spotlight-ring--balance' },
  'tab-market': { padding: 4, radius: 13, ringClass: 'onboarding-spotlight-ring--balance' },
  'shop-showroom': { padding: 8, radius: 14, ringClass: 'onboarding-spotlight-ring--balance' },
  'market-board': { padding: 8, radius: 14, ringClass: 'onboarding-spotlight-ring--balance' },
}

const TAB_BAR_FALLBACK_CLEARANCE = 96
const TAB_SPOTLIGHTS = new Set(['tab-shop', 'tab-market'])

function tabBarClearance() {
  const tab = document.querySelector('.app-tab-bar')
  if (!tab) return TAB_BAR_FALLBACK_CLEARANCE
  return tab.getBoundingClientRect().height + 12
}

function emptyRect() {
  return { top: 0, left: 0, width: 0, height: 0 }
}

function targetSelector(spotlight) {
  switch (spotlight) {
    case 'balance':
      return '#onboarding-balance'
    case 'plot-1':
      return '[data-onboarding-plot="1"]'
    case 'backpack':
      return '#onboarding-backpack'
    case 'tab-shop':
      return '[data-onboarding-tab="shop"]'
    case 'tab-market':
      return '[data-onboarding-tab="market"]'
    case 'shop-showroom':
      return '#onboarding-shop-showroom'
    case 'market-board':
      return '#onboarding-market-board'
    default:
      return null
  }
}

function resolveSpotlightNode(spotlight) {
  if (spotlight === 'backpack') {
    const section = document.getElementById('onboarding-backpack')
    return section?.closest('.inventory-board-frame') ?? section?.closest('.farm-vine-frame') ?? section
  }

  if (spotlight === 'shop-showroom') {
    const section = document.getElementById('onboarding-shop-showroom')
    return section?.closest('.shop-exchange-frame') ?? section
  }

  if (spotlight === 'market-board') {
    const section = document.getElementById('onboarding-market-board')
    return section?.closest('.market-board-frame') ?? section
  }

  const selector = targetSelector(spotlight)
  if (!selector) return null
  return document.querySelector(selector)
}

function measureBalanceRect(padding) {
  const container = document.querySelector('#onboarding-balance')
  if (!container) return emptyRect()

  const chips = container.querySelectorAll('.farm-stat-bar')
  if (!chips.length) return emptyRect()

  let minTop = Infinity
  let minLeft = Infinity
  let maxRight = -Infinity
  let maxBottom = -Infinity

  chips.forEach((chip) => {
    const box = chip.getBoundingClientRect()
    minTop = Math.min(minTop, box.top)
    minLeft = Math.min(minLeft, box.left)
    maxRight = Math.max(maxRight, box.right)
    maxBottom = Math.max(maxBottom, box.bottom)
  })

  return clampSpotlightRect({
    top: Math.max(0, minTop - padding),
    left: Math.max(0, minLeft - padding),
    width: maxRight - minLeft + padding * 2,
    height: maxBottom - minTop + padding * 2,
  })
}

function measureNodeRect(node, padding, { allowTabBar = false } = {}) {
  const box = node.getBoundingClientRect()
  return clampSpotlightRect({
    top: Math.max(0, box.top - padding),
    left: Math.max(0, box.left - padding),
    width: box.width + padding * 2,
    height: box.height + padding * 2,
  }, { allowTabBar })
}

function clampSpotlightRect(rect, { allowTabBar = false } = {}) {
  if (rect.width <= 0 || rect.height <= 0) return rect

  const minTop = 6
  const maxBottom = allowTabBar
    ? window.innerHeight - 4
    : window.innerHeight - tabBarClearance()
  let { top, left, width, height } = rect

  if (top < minTop) {
    height = Math.max(32, height - (minTop - top))
    top = minTop
  }

  if (!allowTabBar && top + height > maxBottom) {
    height = Math.max(32, maxBottom - top)
  }

  return { top, left, width, height }
}

export default function OnboardingSpotlight({
  spotlight,
  ringMode = 'default',
  onTraceComplete,
}) {
  const [rect, setRect] = useState(emptyRect)
  const targetRef = useRef(null)
  const traceDoneRef = useRef(false)
  const config = SPOTLIGHT_CONFIG[spotlight] ?? {
    padding: DEFAULT_PADDING,
    radius: DEFAULT_RADIUS,
  }

  const measure = useCallback(() => {
    if (!spotlight) {
      setRect(emptyRect())
      return
    }

    if (spotlight === 'balance') {
      setRect(measureBalanceRect(config.padding))
      return
    }

    const node = resolveSpotlightNode(spotlight)
    if (!node) {
      targetRef.current = null
      setRect(emptyRect())
      return
    }
    targetRef.current = node
    const allowTabBar = TAB_SPOTLIGHTS.has(spotlight)
    setRect(measureNodeRect(node, config.padding, { allowTabBar }))
  }, [spotlight, config.padding])

  useLayoutEffect(() => {
    measure()
    const onLayout = () => measure()
    window.addEventListener('resize', onLayout)
    window.addEventListener('scroll', onLayout, true)
    return () => {
      window.removeEventListener('resize', onLayout)
      window.removeEventListener('scroll', onLayout, true)
      const node = targetRef.current
      node?.classList.remove('onboarding-spotlight-target')
    }
  }, [measure, spotlight])

  useLayoutEffect(() => {
    const node = targetRef.current
    if (!node) return undefined
    if (ringMode === 'trace' || ringMode === 'glow' || ringMode === 'default') {
      node.classList.add('onboarding-spotlight-target')
    }
    return () => {
      node.classList.remove('onboarding-spotlight-target')
    }
  }, [spotlight, ringMode, rect.width, rect.height])

  useLayoutEffect(() => {
    traceDoneRef.current = false
  }, [spotlight, ringMode])

  useLayoutEffect(() => {
    if (ringMode !== 'trace' || !onTraceComplete) return undefined
    const timer = window.setTimeout(() => {
      if (!traceDoneRef.current) {
        traceDoneRef.current = true
        onTraceComplete()
      }
    }, 5600)
    return () => window.clearTimeout(timer)
  }, [ringMode, onTraceComplete, rect.width])

  const handleTraceEnd = () => {
    if (traceDoneRef.current) return
    traceDoneRef.current = true
    onTraceComplete?.()
  }

  if (!spotlight) return null

  const panelClass = 'onboarding-spotlight-panel'

  if (rect.width <= 0) {
    return (
      <div className="onboarding-spotlight" aria-hidden>
        <div className={`${panelClass} onboarding-spotlight-panel--full`} />
      </div>
    )
  }

  const { top, left, width, height } = rect
  const right = left + width
  const bottom = top + height
  const showGlowRing = ringMode === 'default' || ringMode === 'glow'
  const showTrace = ringMode === 'trace'
  const inset = TRACE_STROKE / 2

  return (
    <div className="onboarding-spotlight" aria-hidden>
      <div className={panelClass} style={{ top: 0, left: 0, right: 0, height: top }} />
      <div className={panelClass} style={{ top: bottom, left: 0, right: 0, bottom: 0 }} />
      <div className={panelClass} style={{ top, left: 0, width: left, height }} />
      <div className={panelClass} style={{ top, left: right, right: 0, height }} />

      {showTrace && (
        <svg
          className="onboarding-spotlight-trace"
          style={{ top, left, width, height }}
          viewBox={`0 0 ${width} ${height}`}
          overflow="visible"
        >
          <rect
            x={inset}
            y={inset}
            width={Math.max(0, width - TRACE_STROKE)}
            height={Math.max(0, height - TRACE_STROKE)}
            rx={config.radius}
            ry={config.radius}
            fill="none"
            className="onboarding-spotlight-trace-stroke"
            pathLength="1"
            strokeDasharray="1"
            strokeDashoffset="1"
            onAnimationEnd={handleTraceEnd}
          />
        </svg>
      )}

      {showGlowRing && (
        <div
          className={[
            'onboarding-spotlight-ring',
            config.ringClass ?? '',
            ringMode === 'glow' ? 'onboarding-spotlight-ring--revealed' : '',
          ].filter(Boolean).join(' ')}
          style={{
            top,
            left,
            width,
            height,
            borderRadius: config.radius,
          }}
        />
      )}
    </div>
  )
}
