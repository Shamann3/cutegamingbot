import { useEffect, useRef, useState } from 'react'
import '../styles/arrival.css'

/**
 * Скролл двери не перехватывается: человек листает саму страницу.
 * onScroll только читает этот скролл и скрабит схему.
 *
 * SCROLL_SYNC: 0.2 — схема ближе к пальцу, 0.4 — мягче.
 * LINE_STAGGER — пауза между линиями. На узком экране она короче.
 */
const SCROLL_SYNC = 0.28
const LINE_STAGGER = 36

function stillMotion() {
  if (typeof window === 'undefined') return true
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches) return true
  return document.body.classList.contains('perf-light')
}

export default function ArrivalStage({ scrollerRef, chapters, revision = '' }) {
  const [active, setActive] = useState(chapters[0]?.id || '')
  const chaptersRef = useRef(chapters)
  chaptersRef.current = chapters
  const activeRef = useRef(active)

  useEffect(() => {
    const scroller = scrollerRef?.current
    if (!scroller || import.meta.env.MODE === 'test' || stillMotion()) return undefined
    let scope = null
    let cancelled = false

    const bind = async () => {
      try {
        const { animate, createScope, createTimeline, stagger, waapi } = await import('animejs')
        const { onScroll } = await import('animejs/events')
        const { createDrawable, morphTo } = await import('animejs/svg')
        if (cancelled || !scroller.isConnected) return
        const root = scroller.querySelector('.arrival-stage')
        const sheet = scroller.querySelector('.gate-sheet')
        if (!root || !sheet) return
        const portrait = window.matchMedia('(orientation: portrait)').matches

        scope = createScope({
          root,
          mediaQueries: { portrait: '(orientation: portrait)' },
        }).add(() => {
          const nodes = root.querySelectorAll('.mech-node')
          if (nodes.length) {
            animate(nodes, {
              scale: [1, 1.2, 1],
              opacity: [0.4, 1, 0.4],
              loop: true,
              duration: 1800,
              delay: stagger(portrait ? 80 : 120),
              ease: 'inOutSine',
            })
          }

          const page = {
            container: scroller,
            target: sheet,
            enter: 'top top',
            leave: 'bottom bottom',
            sync: SCROLL_SYNC,
            onUpdate() {
              const list = chaptersRef.current
              const line = scroller.scrollTop + 96
              let next = list[0]?.id || ''
              for (const chapter of list) {
                const el = scroller.querySelector(`[data-arrival="${chapter.id}"]`)
                if (!el) continue
                const top = el.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop
                if (top <= line) next = chapter.id
              }
              if (next !== activeRef.current) {
                activeRef.current = next
                setActive(next)
              }
            },
          }

          const paths = root.querySelectorAll(portrait ? '.mech-path:not(.mech-dense)' : '.mech-path')
          if (paths.length) {
            animate(createDrawable(paths), {
              draw: ['0 0.2', '0 1'],
              delay: stagger(portrait ? 18 : LINE_STAGGER),
              ease: 'inOut(3)',
              autoplay: onScroll(page),
            })
          }

          const shape = root.querySelector('.mech-shape')
          const assembled = root.querySelector('.mech-shape--assembled')
          if (shape && assembled) {
            animate(shape, {
              d: morphTo(assembled),
              ease: 'inOut(3)',
              autoplay: onScroll({ ...page, sync: 0.36 }),
            })
          }

          createTimeline({
            defaults: { ease: 'linear', duration: 600 },
            autoplay: onScroll(page),
          }).add(root.querySelectorAll('.mech-layer'), {
            rotate: [0, portrait ? 14 : 64],
            opacity: [0.9, 0.34],
          }, 0)

          const pieces = scroller.querySelectorAll('.arrival-dock .auth-form > *, .arrival-dock .auth-tabs, .arrival-dock .entry-back')
          if (pieces.length) {
            waapi.animate(pieces, {
              y: [28, 0],
              opacity: [0.4, 1],
              delay: stagger(portrait ? 40 : 70),
              ease: 'out(3)',
              autoplay: onScroll({
                container: scroller,
                target: scroller.querySelector('.arrival-dock') || sheet,
                enter: 'bottom bottom',
                leave: 'center center',
                sync: 0.25,
              }),
            })
          }
        })
      } catch (err) {
        console.warn('[arrival]', err)
      }
    }

    bind()
    return () => {
      cancelled = true
      scope?.revert()
    }
  }, [scrollerRef, revision])

  const go = (chapter) => {
    const scroller = scrollerRef?.current
    const el = scroller?.querySelector(`[data-arrival="${chapter.id}"]`)
    if (el && !stillMotion()) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    } else if (el) {
      el.scrollIntoView({ behavior: 'auto', block: 'start' })
    }
    chapter.onPick?.()
  }

  return (
    <div className="arrival-stage">
      <svg className="arrival-mech" viewBox="0 0 1200 800" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
        <g className="mech-layer">
          <path className="mech-path" d="M70 160 H400 L500 250 H900" />
          <path className="mech-path" d="M110 320 H360 L460 430 H980" />
          <path className="mech-path" d="M150 540 H620 L710 640 H1100" />
          <path className="mech-path mech-dense" d="M220 90 V280 H480 V560" />
          <path className="mech-path mech-dense" d="M760 120 V300 H1000 V660" />
          <circle className="mech-node" cx="400" cy="160" r="5" />
          <circle className="mech-node" cx="500" cy="250" r="4" />
          <circle className="mech-node" cx="360" cy="320" r="4" />
          <circle className="mech-node mech-dense" cx="620" cy="540" r="5" />
          <path className="mech-shape" d="M160 200 C240 90 380 80 460 190 C560 80 700 130 720 250 C780 380 580 450 450 370 C310 460 90 350 160 200 Z" />
          <path className="mech-shape--assembled" d="M260 160 C340 120 440 120 510 180 C570 130 660 170 650 250 C700 330 600 400 510 370 C420 420 290 380 280 290 C220 260 200 200 260 160 Z" />
        </g>
      </svg>
      <nav className="arrival-nav" aria-label="Путь входа">
        {chapters.map((chapter) => (
          <button
            key={chapter.id}
            type="button"
            className={active === chapter.id ? 'is-on' : ''}
            aria-current={active === chapter.id ? 'step' : undefined}
            onClick={() => go(chapter)}
          >
            {chapter.label}
          </button>
        ))}
      </nav>
    </div>
  )
}
