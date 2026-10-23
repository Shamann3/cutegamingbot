import { useEffect, useRef } from 'react'
import { animate, createScope, createTimeline, stagger, waapi } from 'animejs'
import { onScroll } from 'animejs/events'
import { createDrawable, morphTo } from 'animejs/svg'
import '../styles/epsilon-mechanism.css'

/**
 * Живая схема Эпсилона.
 *
 * Скролл страницы не перехватывается: onScroll только читает уже идущий скролл
 * колонки или оболочки и скрабит таймлайн.
 *
 * Как крутить ощущение:
 * - sync 0.2 — схема почти сразу за пальцем, 0.4 — мягче и инерционнее
 * - duration у таймлайна — насколько долго слой крутится по всему скроллу
 * - stagger(40) — пауза между линиями; на телефоне она короче
 */
const SCROLL_SYNC = 0.28
const LINE_STAGGER = 40
const BAR_STAGGER = 60

function stillMotion() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
    || document.body.classList.contains('perf-light')
}

function pageScroller(el) {
  if (!(el instanceof Element)) return false
  if (el.closest('.eps-mech')) return false
  const tag = el.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return false
  if (el.clientHeight < 240) return false
  return el.scrollHeight > el.clientHeight + 24
}

function findScroller() {
  const phone = document.documentElement.dataset.viewport === 'phone'
  const shell = document.querySelector('.panel-shell')
  if (phone && pageScroller(shell)) return shell
  const layout = document.querySelector('.panel-layout')
  if (layout) {
    for (const child of layout.children) {
      if (pageScroller(child)) return child
    }
  }
  if (pageScroller(shell)) return shell
  const doc = document.scrollingElement
  if (pageScroller(doc)) return doc
  return null
}

function trackOf(scroller) {
  if (!scroller) return null
  let best = null
  let bestH = 0
  for (const child of scroller.children) {
    if (child.classList?.contains('eps-mech')) continue
    const h = child.scrollHeight || child.offsetHeight || 0
    if (h > bestH) {
      best = child
      bestH = h
    }
  }
  return best
}

export default function EpsilonMechanism() {
  const rootRef = useRef(null)
  const scopeRef = useRef(null)

  useEffect(() => {
    const root = rootRef.current
    if (!root) return undefined
    let scroller = null

    const paint = (next) => {
      scopeRef.current?.revert()
      scopeRef.current = null
      scroller = next
      if (stillMotion()) {
        root.dataset.still = '1'
        document.documentElement.classList.remove('eps-scrolled')
        return
      }
      delete root.dataset.still
      const track = trackOf(scroller)
      try {
      scopeRef.current = createScope({
        root,
        mediaQueries: { portrait: '(orientation: portrait)' },
      }).add(({ matches }) => {
        const isPortrait = Boolean(matches.portrait)
        const lineDelay = isPortrait ? 22 : LINE_STAGGER

        animate(root.querySelectorAll('.mech-node'), {
          scale: [1, 1.22, 1],
          opacity: [0.35, 1, 0.35],
          loop: true,
          alternate: true,
          duration: 1800,
          delay: stagger(isPortrait ? 80 : 120),
          ease: 'inOutSine',
        })

        const scroll = {
          container: scroller || undefined,
          target: track || root,
          enter: 'top top',
          leave: 'bottom bottom',
          sync: SCROLL_SYNC,
          onUpdate(self) {
            document.documentElement.classList.toggle('eps-scrolled', self.progress > 0.06)
          },
        }

        const tl = createTimeline({
          defaults: { ease: 'linear', duration: 700 },
          autoplay: onScroll(scroll),
        })
        tl.add(root.querySelectorAll('.mech-layer'), {
          rotate: [0, isPortrait ? 16 : 72],
          opacity: [0.85, 0.28],
        }, 0)

        const paths = root.querySelectorAll(isPortrait ? '.mech-path:not(.mech-dense)' : '.mech-path')
        if (paths.length) {
          animate(createDrawable(paths), {
            draw: ['0 0.12', '0 1'],
            delay: stagger(lineDelay),
            ease: 'inOut(3)',
            autoplay: onScroll({ ...scroll, sync: SCROLL_SYNC }),
          })
        }

        const shape = root.querySelector('.mech-shape')
        const assembled = root.querySelector('.mech-shape--assembled')
        if (shape && assembled) {
          animate(shape, {
            d: morphTo(assembled),
            ease: 'inOut(3)',
            autoplay: onScroll({ ...scroll, sync: 0.36 }),
          })
        }

        waapi.animate(root.querySelectorAll(isPortrait ? '.mech-bar:not(.mech-bar-extra)' : '.mech-bar'), {
          scaleY: [0.2, 1],
          transformOrigin: 'bottom',
          delay: stagger(isPortrait ? 40 : BAR_STAGGER),
          ease: 'out(2)',
          autoplay: onScroll({ ...scroll, sync: SCROLL_SYNC }),
        })
      })
      } catch (err) {
        console.warn('[epsilon]', err)
        root.dataset.still = '1'
      }
    }

    paint(findScroller())

    const onScrollCapture = (event) => {
      const el = event.target
      if (el === scroller || !pageScroller(el)) return
      paint(el)
    }
    document.addEventListener('scroll', onScrollCapture, true)

    const perf = new MutationObserver(() => {
      const nextStill = stillMotion()
      const wasStill = root.dataset.still === '1'
      if (nextStill !== wasStill) paint(findScroller())
    })
    perf.observe(document.body, { attributes: true, attributeFilter: ['class'] })

    return () => {
      document.removeEventListener('scroll', onScrollCapture, true)
      perf.disconnect()
      scopeRef.current?.revert()
      scopeRef.current = null
      document.documentElement.classList.remove('eps-scrolled')
    }
  }, [])

  return (
    <div ref={rootRef} className="eps-mech" aria-hidden="true">
      <svg className="eps-mech-svg" viewBox="0 0 1200 800" preserveAspectRatio="xMidYMid slice">
        <g className="mech-layer">
          <path className="mech-path" d="M80 140 H420 L520 240 H860" />
          <path className="mech-path" d="M120 260 H380 L470 360 H980" />
          <path className="mech-path" d="M160 480 H640 L720 560 H1080" />
          <path className="mech-path mech-dense" d="M200 80 V300 H460 V520" />
          <path className="mech-path mech-dense" d="M700 100 V280 H980 V640" />
          <path className="mech-path mech-dense" d="M80 620 H300 L390 700 H760" />
          <circle className="mech-node" cx="420" cy="140" r="5" />
          <circle className="mech-node" cx="520" cy="240" r="4" />
          <circle className="mech-node" cx="380" cy="260" r="4" />
          <circle className="mech-node mech-dense" cx="640" cy="480" r="5" />
          <circle className="mech-node mech-dense" cx="720" cy="560" r="4" />
          <path
            className="mech-shape"
            d="M140 180 C220 80 340 70 420 170 C520 60 680 110 700 230 C760 360 560 430 430 360 C300 450 80 340 140 180 Z"
          />
          <path
            className="mech-shape--assembled"
            d="M250 150 C330 110 430 110 500 170 C560 120 650 160 640 240 C690 320 590 390 500 360 C410 410 280 370 270 280 C210 250 190 190 250 150 Z"
          />
        </g>
        <g className="mech-layer mech-dense">
          <path className="mech-path mech-dense" d="M40 400 H180 M1020 180 H1160 M900 700 H1120" />
          <circle className="mech-node mech-dense" cx="180" cy="400" r="3" />
          <circle className="mech-node mech-dense" cx="1020" cy="180" r="3" />
        </g>
      </svg>
      <div className="eps-mech-bars">
        <span className="mech-bar" />
        <span className="mech-bar" />
        <span className="mech-bar" />
        <span className="mech-bar" />
        <span className="mech-bar mech-bar-extra" />
        <span className="mech-bar mech-bar-extra" />
        <span className="mech-bar mech-bar-extra" />
      </div>
    </div>
  )
}
