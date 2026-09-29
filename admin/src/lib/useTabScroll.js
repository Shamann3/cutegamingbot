import { useEffect } from 'react'

const SKIP_TAG = new Set(['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON', 'IMG', 'SVG', 'CANVAS', 'VIDEO', 'IFRAME'])
const SKIP_CLOSEST = 'textarea, select, [contenteditable="true"], [role="dialog"], [role="listbox"], .metric-sheet, .case-backdrop, .accent-picker-panel, .elite-search-results'

function wheelPixels(event) {
  if (event.deltaMode === 1) return event.deltaY * 16
  if (event.deltaMode === 2) return event.deltaY * window.innerHeight
  return event.deltaY
}

export function releaseNestedScrolls(main) {
  const nodes = main.querySelectorAll('div, section, article, ul, ol, nav, table')
  const list = [...nodes].reverse()
  for (let pass = 0; pass < 3; pass += 1) {
    for (const node of list) {
      if (SKIP_TAG.has(node.tagName)) continue
      if (node.closest(SKIP_CLOSEST)) continue
      const style = getComputedStyle(node)
      const y = style.overflowY
      const scrolls = y === 'auto' || y === 'scroll'
      const clips = (y === 'hidden' || y === 'clip')
        && node.clientHeight > 140
        && node.scrollHeight > node.clientHeight + 32
        && (style.maxHeight !== 'none' || style.height.endsWith('%') || node.scrollHeight > node.clientHeight + 80)
      if (!scrolls && !clips) continue
      if (node.classList?.contains('users-toolbar') || node.classList?.contains('nika-seg')) {
        node.style.setProperty('max-height', 'none', 'important')
        node.style.setProperty('overflow', 'visible', 'important')
        continue
      }
      node.style.setProperty('max-height', 'none', 'important')
      node.style.setProperty('height', 'auto', 'important')
      const wide = node.scrollWidth > node.clientWidth + 8
      const shortStrip = node.clientHeight > 0 && node.clientHeight <= 72
      if (wide && shortStrip) {
        node.style.setProperty('overflow-x', 'auto', 'important')
        node.style.setProperty('overflow-y', 'hidden', 'important')
        continue
      }
      node.style.setProperty('overflow', 'visible', 'important')
    }
  }
}

/** Одна прокрутка вкладки. Колесо в любой точке рабочей области двигает её. */
export function useTabScroll(mainRef, tabKey) {
  useEffect(() => {
    const main = mainRef.current
    if (!main) return undefined
    main.scrollTop = 0

    let frame = 0
    const release = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => releaseNestedScrolls(main))
    }
    release()
    const observer = new MutationObserver(release)
    observer.observe(main, { childList: true, subtree: true })

    const onWheel = (event) => {
      if (event.ctrlKey || event.metaKey) return
      if (Math.abs(event.deltaX) > Math.abs(event.deltaY)) return
      const target = event.target
      if (!(target instanceof Node) || !main.contains(target)) return
      if (target instanceof Element && target.closest(SKIP_CLOSEST)) return
      const delta = wheelPixels(event)
      if (!delta) return
      const max = main.scrollHeight - main.clientHeight
      if (max <= 1) return
      if (delta < 0 && main.scrollTop <= 0) return
      if (delta > 0 && main.scrollTop >= max - 1) return
      event.preventDefault()
      main.scrollTop = Math.min(max, Math.max(0, main.scrollTop + delta))
    }
    window.addEventListener('wheel', onWheel, { capture: true, passive: false })

    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
      window.removeEventListener('wheel', onWheel, { capture: true })
    }
  }, [mainRef, tabKey])
}
