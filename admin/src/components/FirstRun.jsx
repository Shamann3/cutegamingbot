import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { coachFrame, placeCoachCard } from '../lib/coachPlace'

export function staffSteps(phone) {
  return [
    {
      title: 'Нижняя полоса',
      body: 'Это кнопки разделов. Нажмите «Игроки», «Архив» или «Поддержка». Разделы, которых нет на полосе, лежат в кнопке «Ещё».',
      target: '[data-coach="dock"]',
    },
    {
      title: 'Поиск раздела',
      body: phone
        ? 'Откройте «Ещё» и введите название. Нужный раздел откроется сразу, листать сетку не нужно.'
        : 'Введите название раздела в поиск слева. Он откроется сразу.',
      target: phone ? '[data-coach="dock"] [data-section="more"]' : '[data-coach="search"]',
    },
    {
      title: 'Игроки',
      body: 'Карточка человека: баланс, предметы и история. Запрет на весь проект есть только у должности, которой это право включили.',
      target: '[data-coach="dock"] [data-section="users"]',
    },
    {
      title: 'Поддержка',
      body: 'Здесь письма игроков. Число на колокольчике — сколько писем ещё без ответа.',
      target: '[data-coach="bell"], [data-coach="dock"] [data-section="support"]',
    },
    {
      title: 'Сменить панель',
      body: phone
        ? 'Смена панели — внизу «Ещё». Аккаунт не закрывается, вы возвращаетесь к выбору: сотрудник или группа.'
        : 'Кнопка слева внизу возвращает к выбору: сотрудник или группа. Из аккаунта вы не выходите.',
      target: phone ? '[data-coach="dock"] [data-section="more"]' : '[data-coach="doors"]',
    },
  ]
}

export function workLessonSteps(kind) {
  if (kind === 'creator') {
    return [
      {
        title: 'Вкладка «Работа»',
        body: 'Она стоит рядом с «Главная» и «Архив». Здесь наказания, которые уже проверил администратор группы или сотрудник проекта. Второго ответа можно не ждать.',
        target: '[data-coach="dock"] [data-section="work"]',
        openSection: 'work',
      },
      {
        title: 'Зарплата',
        body: 'Вправо сразу отправляет в зарплату того, кто выдал, и кто сказал «подходит». Влево засчитывает «неправильно». Кто проверял — администратор или сотрудник — не важно.',
        target: '.work-page',
        openSection: 'work',
      },
    ]
  }
  if (kind === 'group') {
    return [
      {
        title: 'Вкладка «Работа»',
        body: 'Она стоит рядом с «Главная» и «Архив». В этой вкладке показываются наказания со всего проекта. Ваша задача - проверить правильно ли выдано наказание, и отправить результат. После вашей проверки - наказание которое вы проверите будет перепроверять сотрудник проекта, и потом создатель проекта',
        target: '[data-coach="dock"] [data-section="work"]',
        openSection: 'work',
      },
      {
        title: 'Три ответа',
        body: 'Вправо — подходит. Влево — выдано неправильно, тогда можно просить снять. Вниз — непонятно. Дальше карточку берёт один из сотрудников проекта, затем создатель. Зарплата придёт вам в том случае если наказание которое вы проверили пройдет весь цикл проверок, от вас, до создателя проекта',
        target: '.work-desk',
        openSection: 'work',
      },
    ]
  }
  return [
    {
      title: 'Вкладка «Работа»',
      body: 'Она стоит рядом с «Главная» и «Архив». В этой вкладке показываются наказания со всего проекта. Ваша задача - проверить правильно ли выдано наказание, и отправить результат. После вашей проверки - наказание которое вы проверите будет перепроверять сотрудник проекта, и потом создатель проекта',
      target: '[data-coach="dock"] [data-section="work"]',
      openSection: 'work',
    },
    {
      title: 'Три ответа',
      body: 'Вправо — подходит. Влево — выдано неправильно, тогда можно просить снять. Вниз — непонятно. Дальше карточку берёт один из сотрудников проекта, затем создатель. Зарплата придёт вам в том случае если наказание которое вы проверили пройдет весь цикл проверок, от вас, до создателя проекта',
      target: '.work-desk',
      openSection: 'work',
    },
  ]
}

export function groupSteps(phone) {
  return [
    {
      title: 'Добро пожаловать',
      body: 'Сейчас вы находитесь на главной вкладке Админ панели Эпсилона, здесь находится основная информация о группе, которую вы модерируете.',
      target: '.grp-overview-stats',
    },
    {
      title: 'Вкладки',
      body: phone
        ? 'Снизу вы можете выбрать любую доступную вам вкладку для использования'
        : 'Смена интерфейса слева от остальных вкладок в настройках',
      target: '[data-coach="dock"]',
    },
    {
      title: 'Активность',
      body: 'Сообщения за день, месяц и год в группе которую вы модерируете',
      target: '[data-coach="dock"] [data-section="activity"]',
    },
    {
      title: 'Дополнительные вкладки',
      body: phone
        ? 'Во вкладке "Ещё" вы сможете открыть дополнительные вкладки для удобной работы'
        : 'Там же можно прочесть правила групп в проекте.',
      target: '[data-coach="dock"] [data-section="more"]',
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

function spotRadius(node) {
  const radius = getComputedStyle(node).borderRadius
  if (!radius || radius === '0px') return '0px'
  return radius
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
    radius: spotRadius(node),
    low: top + height / 2 > window.innerHeight * 0.55,
  }
}

function readChromeTop() {
  const raw = getComputedStyle(document.documentElement).getPropertyValue('--tg-content-top')
  const value = parseFloat(raw)
  return Number.isFinite(value) ? value : 0
}

function readDockTop() {
  const dock = document.querySelector('.panel-shell > .phone-dock, .phone-dock')
  if (!dock) return null
  const rect = dock.getBoundingClientRect()
  if (rect.height < 8 || rect.top > window.innerHeight) return null
  return rect.top
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

function measureCard(card, spot) {
  const viewport = { width: window.innerWidth, height: window.innerHeight }
  const frame = coachFrame(viewport, {
    chromeTop: readChromeTop() + 8,
    dockTop: readDockTop(),
  })
  const width = Math.min(380, frame.right - frame.left)
  return placeCoachCard({
    viewport,
    frame,
    card: { width, height: card?.offsetHeight || 240 },
    spot,
  })
}

export default function FirstRun({ storageKey, steps, onDone, onStep, layoutKey = 0 }) {
  const [index, setIndex] = useState(0)
  const [box, setBox] = useState(null)
  const [place, setPlace] = useState(null)
  const cardRef = useRef(null)
  const nextRef = useRef(null)
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
    nextRef.current?.focus({ preventScroll: true })
  }, [index])

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        event.stopPropagation()
        skipOnce()
      }
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  })

  useEffect(() => {
    document.documentElement.classList.add('is-coaching')
    return () => document.documentElement.classList.remove('is-coaching')
  }, [])

  useEffect(() => {
    let cancelled = false
    let tries = 0
    const measure = () => {
      if (cancelled) return
      const node = visibleTarget(step?.target)
      if (!node) {
        setBox(null)
        // Drawer ещё открывается — не застреваем: ещё попытки, потом идём дальше без рамки
        if (step?.openNav && tries < 8) {
          tries += 1
          window.setTimeout(measure, 120)
        }
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
    const soon = window.setTimeout(measure, step?.openNav ? 280 : 60)
    const afterDrawer = window.setTimeout(measure, step?.openNav ? 700 : 520)
    window.addEventListener('resize', measure)
    return () => {
      cancelled = true
      window.clearTimeout(soon)
      window.clearTimeout(afterDrawer)
      window.removeEventListener('resize', measure)
    }
  }, [step, layoutKey])

  useLayoutEffect(() => {
    const apply = () => setPlace(measureCard(cardRef.current, box))
    apply()
    window.addEventListener('resize', apply)
    return () => window.removeEventListener('resize', apply)
  }, [box, index, step, layoutKey])

  const sheetStyle = place
    ? {
      top: place.top,
      left: place.left,
      width: place.width,
      right: 'auto',
      bottom: 'auto',
      maxHeight: place.maxHeight,
      margin: 0,
    }
    : undefined

  const [shieldClip, setShieldClip] = useState('')

  useLayoutEffect(() => {
    const card = cardRef.current?.getBoundingClientRect()
    const holes = []
    const cardBox = card && card.width > 8 && card.height > 8
      ? [card.left, card.top, card.right, card.bottom]
      : null
    if (box) {
      const spot = [box.left, box.top, box.left + box.width, box.top + box.height]
      if (!cardBox || !rectsOverlap(spot, cardBox)) holes.push(spot)
    }
    if (cardBox) holes.push(cardBox)
    setShieldClip(holes.length ? shieldHole(holes) : '')
  }, [place, box])

  return (
    <div className={`firstrun${box ? ' has-spot' : ''}`} role="dialog" aria-modal="true" aria-labelledby="firstrun-title">
      <div className="firstrun-shield" style={shieldClip ? { clipPath: shieldClip } : undefined} />
      {box && (
        <div
          className="firstrun-spot"
          style={{ top: box.top, left: box.left, width: box.width, height: box.height, borderRadius: box.radius || '0px' }}
        />
      )}
      <div className="firstrun-sheet is-anchored" style={sheetStyle} ref={cardRef}>
        <p className="firstrun-progress">{index + 1} из {steps.length}</p>
        <h2 id="firstrun-title" className="firstrun-title">{step.title}</h2>
        <p className="firstrun-body">{step.body}</p>
        <div className="firstrun-actions">
          <button type="button" className="firstrun-skip" onClick={skipOnce}>Пропустить</button>
          <button
            type="button"
            className="firstrun-next"
            ref={nextRef}
            onClick={last ? finish : () => setIndex((n) => n + 1)}
          >
            {last ? 'Понятно' : 'Дальше'}
          </button>
          <button type="button" className="firstrun-never" onClick={hideForever}>Не показывать больше</button>
        </div>
      </div>
    </div>
  )
}

function rectsOverlap(a, b) {
  return !(a[2] <= b[0] || a[0] >= b[2] || a[3] <= b[1] || a[1] >= b[3])
}

function shieldHole(holes) {
  const w = Math.round(window.innerWidth)
  const h = Math.round(window.innerHeight)
  const parts = [`M 0 0 H ${w} V ${h} H 0 Z`]
  for (const [left, top, right, bottom] of holes) {
    const l = Math.round(left)
    const t = Math.round(top)
    const r = Math.round(right)
    const b = Math.round(bottom)
    parts.push(`M ${l} ${t} H ${r} V ${b} H ${l} Z`)
  }
  return `path(evenodd, '${parts.join(' ')}')`
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

/** Сбрасывает «уже видел» и «больше не показывать», чтобы тур начался с первого шага. */
export function restartCoach(storageKey) {
  const key = String(storageKey || '')
  try {
    localStorage.removeItem(key)
    localStorage.removeItem(neverKey(key))
    sessionStorage.removeItem(key)
  } catch {
    /* хранилище может быть закрыто */
  }
}
