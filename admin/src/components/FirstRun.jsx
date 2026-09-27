import { useEffect, useState } from 'react'

export function staffSteps(phone) {
  return [
    {
      title: phone ? 'Меню' : 'Страницы',
      body: phone
        ? 'Кнопка справа сверху открывает страницы. Свайп вправо открывает список, свайп влево закрывает.'
        : 'Слева страницы. Нажмите название.',
      target: phone ? '[data-coach="menu"]' : '[data-coach="nav"]',
    },
    {
      title: 'Поиск',
      body: 'Напишите название страницы и откройте её.',
      target: phone ? '.panel-sidebar-search' : '[data-coach="search"]',
      openNav: phone,
    },
    {
      title: 'Игроки',
      body: 'Карточки людей. Запрет на весь проект есть только у должности с этим правом.',
      target: '[data-section="users"]',
      openNav: phone,
    },
    {
      title: 'Сменить панель',
      body: 'Возврат к выбору: сотрудник или группа. Из аккаунта вы не выходите.',
      target: '[data-coach="doors"]',
      openNav: phone,
    },
  ]
}

export function groupSteps(phone) {
  return [
    {
      title: 'Эта группа',
      body: 'Чат, ваша должность и сообщения за 30 дней.',
      target: '.realm-top h1',
    },
    {
      title: 'Страницы',
      body: phone
        ? 'Кнопка меню открывает страницы этой группы.'
        : 'Слева страницы этой группы. Нажмите нужную.',
      target: phone ? '[data-coach="menu"]' : '[data-coach="nav"]',
    },
    {
      title: 'Люди',
      body: 'Наказать можно только того, кто в этом чате младше вас.',
      target: '[data-section="people"]',
      openNav: phone,
    },
    {
      title: 'Ещё',
      body: 'Правила и кнопка «Сменить панель».',
      target: '[data-section="more"]',
      openNav: phone,
    },
  ]
}

const EDGE = 12

function bringIntoView(node) {
  node.scrollIntoView({ block: 'nearest', inline: 'nearest' })
  let parent = node.parentElement
  while (parent && parent !== document.body) {
    const style = window.getComputedStyle(parent)
    const scrollX = /(auto|scroll)/.test(style.overflowX)
    const scrollY = /(auto|scroll)/.test(style.overflowY)
    if (scrollX || scrollY) {
      const parentRect = parent.getBoundingClientRect()
      const rect = node.getBoundingClientRect()
      if (scrollX && rect.left < parentRect.left + 8) parent.scrollLeft -= parentRect.left + 8 - rect.left
      if (scrollX && rect.right > parentRect.right - 8) parent.scrollLeft += rect.right - (parentRect.right - 8)
      if (scrollY && rect.top < parentRect.top + 8) parent.scrollTop -= parentRect.top + 8 - rect.top
      if (scrollY && rect.bottom > parentRect.bottom - 8) parent.scrollTop += rect.bottom - (parentRect.bottom - 8)
    }
    parent = parent.parentElement
  }
}

function spotFor(node) {
  const rect = node.getBoundingClientRect()
  const left = Math.max(EDGE, rect.left)
  const top = Math.max(EDGE, rect.top)
  const right = Math.min(window.innerWidth - EDGE, rect.right)
  const bottom = Math.min(window.innerHeight - EDGE, rect.bottom)
  const width = right - left
  const height = bottom - top
  if (width < 24 || height < 24) return null
  return {
    top,
    left,
    width,
    height,
    low: top + height / 2 > window.innerHeight * 0.55,
  }
}

function blocksCard(card, spot) {
  return !(card.right <= spot.left - 10 || card.left >= spot.right + 10 || card.bottom <= spot.top - 10 || card.top >= spot.bottom + 10)
}

function placeCard(box) {
  const cardW = Math.min(320, window.innerWidth - EDGE * 2)
  const cardH = 200
  const maxRight = window.innerWidth - EDGE
  const maxBottom = window.innerHeight - EDGE
  if (window.innerWidth < 720) {
    return box?.low
      ? { top: EDGE, left: EDGE, right: EDGE, width: 'auto', bottom: 'auto' }
      : { top: 'auto', bottom: EDGE, left: EDGE, right: EDGE, width: 'auto' }
  }
  if (!box) return { top: 'auto', bottom: EDGE, left: EDGE, right: EDGE, width: 'auto' }
  const obstacles = [{
    left: box.left,
    top: box.top,
    right: box.left + box.width,
    bottom: box.top + box.height,
  }]
  document.querySelectorAll('.realm-top, .realm-search, .elite-topbar, .elite-search-wrap').forEach((node) => {
    const rect = node.getBoundingClientRect()
    if (rect.width > 8 && rect.height > 8) obstacles.push(rect)
  })
  const tries = [
    [box.left + box.width + 16, maxBottom - cardH],
    [box.left + box.width + 16, EDGE],
    [maxRight - cardW, maxBottom - cardH],
    [EDGE, maxBottom - cardH],
  ]
  for (const [rawLeft, rawTop] of tries) {
    const left = Math.max(EDGE, Math.min(rawLeft, maxRight - cardW))
    const top = Math.max(EDGE, Math.min(rawTop, maxBottom - cardH))
    const card = { left, top, right: left + cardW, bottom: top + cardH }
    if (card.right > maxRight || card.bottom > maxBottom) continue
    if (obstacles.some((spot) => blocksCard(card, spot))) continue
    return { top, left, width: cardW, right: 'auto', bottom: 'auto' }
  }
  const left = Math.max(EDGE, Math.min(box.left + box.width + 16, maxRight - cardW))
  const top = Math.max(EDGE, maxBottom - cardH)
  return { top, left, width: cardW, right: 'auto', bottom: 'auto' }
}

function onScreen(node) {
  if (!node || node.getClientRects().length === 0) return false
  const style = window.getComputedStyle(node)
  if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) return false
  const rect = node.getBoundingClientRect()
  if (rect.width < 8 || rect.height < 8) return false
  const visibleW = Math.min(rect.right, window.innerWidth) - Math.max(rect.left, 0)
  const visibleH = Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0)
  return visibleW > 16 && visibleH > 16
}

function visibleTarget(selector) {
  if (!selector || typeof document === 'undefined') return null
  const nodes = document.querySelectorAll(selector)
  for (const node of nodes) {
    if (onScreen(node)) return node
  }
  return null
}

export default function FirstRun({ storageKey, steps, onDone, onStep, layoutKey = 0 }) {
  const [index, setIndex] = useState(0)
  const [box, setBox] = useState(null)
  const step = steps[index]
  const last = index >= steps.length - 1

  const finish = () => {
    try {
      localStorage.setItem(storageKey, '1')
    } catch {
      /* ignore */
    }
    onDone?.()
  }

  const skipOnce = () => {
    try {
      sessionStorage.setItem(storageKey, '1')
    } catch {
      /* ignore */
    }
    onDone?.()
  }

  const hideForever = () => {
    try {
      localStorage.setItem(neverKey(storageKey), '1')
    } catch {
      /* ignore */
    }
    onDone?.()
  }

  useEffect(() => {
    onStep?.(step)
  }, [step, onStep])

  useEffect(() => {
    let cancelled = false
    const measure = () => {
      if (cancelled) return
      const node = visibleTarget(step?.target)
      if (!node) {
        setBox(null)
        return
      }
      bringIntoView(node)
      const scroller = node.closest('.realm-tabbar, .panel-sidebar-nav, .realm-rail-sheet')
      if (scroller) {
        const next = node.offsetLeft - (scroller.clientWidth - node.offsetWidth) / 2
        scroller.scrollLeft = Math.max(0, next)
      }
      window.requestAnimationFrame(() => {
        if (cancelled || !onScreen(node)) {
          setBox(null)
          return
        }
        setBox(spotFor(node))
      })
    }
    const soon = window.setTimeout(measure, 60)
    const afterDrawer = window.setTimeout(measure, 520)
    window.addEventListener('resize', measure)
    return () => {
      cancelled = true
      window.clearTimeout(soon)
      window.clearTimeout(afterDrawer)
      window.removeEventListener('resize', measure)
    }
  }, [step, layoutKey])

  const sheetStyle = placeCard(box)

  return (
    <div className={`firstrun${box ? ' has-spot' : ''}`} role="dialog" aria-modal="true" aria-labelledby="firstrun-title">
      {box && (
        <div
          className="firstrun-spot"
          style={{ top: box.top, left: box.left, width: box.width, height: box.height }}
        />
      )}
      <div className={`firstrun-sheet${box ? ' is-anchored' : ''}`} style={sheetStyle}>
        <p className="firstrun-focus">Рамка показывает, куда нажать.</p>
        <h2 id="firstrun-title" className="firstrun-title">{step.title}</h2>
        <p className="firstrun-body">{step.body}</p>
        <div className="firstrun-dots" aria-hidden="true">
          {steps.map((_, i) => (
            <span key={i} className={i === index ? 'is-on' : ''} />
          ))}
        </div>
        <div className="firstrun-actions">
          <button type="button" className="firstrun-never" onClick={hideForever}>Не показывать больше</button>
          <button type="button" className="firstrun-skip" onClick={skipOnce}>Пропустить сейчас</button>
          <button type="button" className="firstrun-next" onClick={last ? finish : () => setIndex((n) => n + 1)}>
            {last ? 'Понятно' : 'Дальше'}
          </button>
        </div>
      </div>
    </div>
  )
}

function neverKey(storageKey) {
  return `${String(storageKey).replace(/\.v\d+$/, '')}.never`
}

export function firstRunSeen(storageKey) {
  try {
    return localStorage.getItem(storageKey) === '1'
  } catch {
    return true
  }
}

export function firstRunNever(storageKey) {
  try {
    return localStorage.getItem(neverKey(storageKey)) === '1'
  } catch {
    return true
  }
}

export function coachClosed(storageKey) {
  try {
    if (firstRunNever(storageKey) || firstRunSeen(storageKey)) return true
    return sessionStorage.getItem(storageKey) === '1'
  } catch {
    return true
  }
}
