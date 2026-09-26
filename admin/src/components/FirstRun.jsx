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
      body: 'Белая рамка вокруг заголовка. Это панель одной группы. Под заголовком — название чата, ваша должность и сколько сообщений было за 30 дней.',
      target: '[data-coach="group-head"]',
    },
    {
      title: 'Страницы группы',
      body: phone
        ? 'Белая рамка вокруг кнопок внизу. Нажмите нужную. Свайп вправо открывает тот же список, свайп влево плавно его закрывает.'
        : 'Белая рамка вокруг списка слева. Нажмите: обзор, люди, архив или цифры. Каждая страница про эту группу.',
      target: phone ? '.realm-tabbar' : '.realm-rail',
    },
    {
      title: 'Наказание',
      body: 'Нажмите «Люди». Наказать можно только того, кто в этом чате младше вас. Равного и старшего система не пропустит.',
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
      node.scrollIntoView({ block: 'center', inline: 'nearest' })
      window.requestAnimationFrame(() => {
        if (cancelled || !onScreen(node)) {
          setBox(null)
          return
        }
        const rect = node.getBoundingClientRect()
        const pad = 8
        const top = rect.top - pad
        const height = rect.height + pad * 2
        setBox({
          top,
          left: Math.max(8, rect.left - pad),
          width: Math.min(window.innerWidth - 16, rect.width + pad * 2),
          height,
          below: top + height + 210 < window.innerHeight,
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

  const sheetStyle = box
    ? (box.below
      ? { top: box.top + box.height + 14, bottom: 'auto' }
      : { top: 'auto', bottom: Math.max(16, window.innerHeight - box.top + 14) })
    : undefined

  return (
    <div className={`firstrun${box ? ' has-spot' : ''}`} role="dialog" aria-modal="true" aria-labelledby="firstrun-title">
      {box && (
        <div
          className="firstrun-spot"
          style={{ top: box.top, left: box.left, width: box.width, height: box.height }}
        />
      )}
      <div className={`firstrun-sheet${box ? ' is-anchored' : ''}`} style={sheetStyle}>
        <p className="firstrun-focus">Белая рамка показывает место. Это не ошибка экрана.</p>
        <h2 id="firstrun-title" className="firstrun-title">{step.title}</h2>
        <p className="firstrun-body">{step.body}</p>
        <div className="firstrun-dots" aria-hidden="true">
          {steps.map((_, i) => (
            <span key={i} className={i === index ? 'is-on' : ''} />
          ))}
        </div>
        <div className="firstrun-actions">
          <button type="button" className="firstrun-skip" onClick={finish}>Пропустить</button>
          <button type="button" className="firstrun-next" onClick={last ? finish : () => setIndex((n) => n + 1)}>
            {last ? 'Понятно' : 'Дальше'}
          </button>
        </div>
      </div>
    </div>
  )
}

export function firstRunSeen(storageKey) {
  try {
    return localStorage.getItem(storageKey) === '1'
  } catch {
    return true
  }
}
