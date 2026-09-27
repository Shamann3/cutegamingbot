import { useEffect, useState } from 'react'

export function staffSteps(phone) {
  return [
    {
      title: phone ? 'Кнопка меню' : 'Главная',
      body: phone
        ? 'Белая рамка вокруг кнопки меню справа сверху. Нажмите её или смахните вправо. Откроется список страниц. Смахните влево, и список плавно закроется.'
        : 'Белая рамка вокруг «Главная». Слева список страниц. Нажмите название, и откроется эта страница.',
      target: phone ? '[data-coach="menu"]' : '[data-section="dashboard"]',
    },
    {
      title: 'Поиск страницы',
      body: phone
        ? 'Белая рамка вокруг поля «Найти раздел». Напишите слово, например «игроки», и нажмите найденную строку.'
        : 'Белая рамка вокруг поля поиска справа вверху. Напишите название страницы и нажмите Enter. С клавиатуры это Ctrl и K.',
      target: phone ? '.panel-sidebar-search' : '[data-coach="search"]',
      openNav: phone,
    },
    {
      title: 'Игроки',
      body: 'Белая рамка вокруг «Игроки». Там карточки людей. Запретить человека во всём проекте можно только если у вашей должности есть это право.',
      target: '[data-section="users"]',
      openNav: phone,
    },
    {
      title: 'Сменить панель',
      body: 'Белая рамка вокруг «Сменить панель». Она возвращает к выбору: панель сотрудника или панель группы. Из аккаунта вы не выходите.',
      target: '[data-coach="doors"]',
      openNav: phone,
    },
  ]
}

export function groupSteps(phone) {
  return [
    {
      title: 'Где вы',
      body: 'Рамка вокруг названия. Это панель одной группы: чат, ваша должность и сообщения за 30 дней.',
      target: '.realm-top h1',
    },
    {
      title: 'Страницы группы',
      body: phone
        ? 'Белая рамка вокруг кнопок внизу. Нажмите нужную. Свайп вправо открывает тот же список, свайп влево плавно его закрывает.'
        : 'Белая рамка вокруг списка слева. Нажмите: обзор, люди, архив или цифры. Каждая страница про эту группу.',
      target: phone ? '.realm-tabbar' : '.realm-rail',
    },
    {
      title: 'Люди',
      body: 'Нажмите кнопку «Люди». Наказать можно только того, кто в этом чате младше вас. Равного и старшего система не пропустит.',
      target: '[data-coach="people"]',
    },
    {
      title: 'Правила',
      body: 'Нажмите «Ещё». Там ссылка на правила и кнопка «Сменить панель».',
      target: '[data-coach="more"]',
    },
  ]
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
      node.scrollIntoView({ block: 'center', inline: 'center' })
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
        const rect = node.getBoundingClientRect()
        const margin = 10
        const left = Math.max(margin, rect.left - 6)
        const top = Math.max(margin, rect.top - 6)
        const right = Math.min(window.innerWidth - margin, rect.right + 6)
        const bottom = Math.min(window.innerHeight - margin, rect.bottom + 6)
        const width = right - left
        const height = bottom - top
        if (width < 28 || height < 28 || height > 180) {
          setBox(null)
          return
        }
        setBox({
          top,
          left,
          width,
          height,
          low: top > window.innerHeight * 0.5,
        })
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

  const sheetStyle = (() => {
    const edge = 12
    const stacked = (low) => (
      low
        ? { top: 'calc(var(--tg-content-top, 0px) + 12px)', bottom: 'auto', left: edge, right: edge, width: 'auto' }
        : { top: 'auto', bottom: 'calc(var(--tg-content-bottom, 0px) + 12px)', left: edge, right: edge, width: 'auto' }
    )
    if (window.innerWidth < 720) return stacked(Boolean(box?.low))
    if (!box) return undefined
    const width = 320
    const left = box.left + box.width + edge
    if (left + width <= window.innerWidth - edge) {
      return {
        top: Math.min(Math.max(edge, box.top), Math.max(edge, window.innerHeight - 280)),
        left,
        right: 'auto',
        width,
        bottom: 'auto',
      }
    }
    return stacked(box.low)
  })()

  return (
    <div className={`firstrun${box ? ' has-spot' : ''}`} role="dialog" aria-modal="true" aria-labelledby="firstrun-title">
      {box && (
        <div
          className="firstrun-spot"
          style={{ top: box.top, left: box.left, width: box.width, height: box.height }}
        />
      )}
      <div className={`firstrun-sheet${box ? ' is-anchored' : ''}`} style={sheetStyle}>
        <p className="firstrun-focus">Рамка показывает место. Это не ошибка экрана.</p>
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
