import { useEffect, useState } from 'react'

export function staffSteps(phone) {
  return [
    {
      title: 'Разделы',
      body: phone
        ? 'Смахните вправо или нажмите полоску слева. Список закроется свайпом влево.'
        : 'Разделы уже слева. Нажмите название, и откроется эта часть панели.',
      target: '[data-coach="menu"], [data-coach="nav"]',
    },
    {
      title: 'Поиск',
      body: phone
        ? 'В списке разделов есть поле «Найти раздел». Наберите название и выберите его.'
        : 'Справа в шапке поле «Поиск раздела». Наберите название и нажмите Enter. С клавиатуры это Ctrl+K.',
      target: '[data-coach="search"], .panel-sidebar-search',
      openNav: phone,
    },
    {
      title: 'Игроки',
      body: 'Нажмите «Игроки». Бан на весь проект там есть только у должности с правом банфулл.',
      target: '[data-section="users"]',
      openNav: phone,
    },
    {
      title: 'Двери',
      body: 'Нажмите «Двери». Снова спросит, куда войти: панель сотрудника или панель группы. Из аккаунта это не выходит.',
      target: '[data-coach="doors"]',
      openNav: phone,
    },
  ]
}

export function groupSteps(phone) {
  return [
    {
      title: 'Где вы',
      body: 'Это панель администраторов групп. Под заголовком — чат, ваша должность и сообщения за 30 дней. Цифры только этой группы.',
      target: '[data-coach="group-head"]',
    },
    {
      title: 'Вкладки',
      body: phone
        ? 'Вкладки внизу. Свайп вправо открывает полный список, влево его закрывает.'
        : 'Вкладки слева. Нажмите нужную: обзор, люди, архив, аналитика.',
      target: '[data-coach="tabs"]',
    },
    {
      title: 'Наказание',
      body: 'Нажмите «Люди». Наказать можно только того, кто в этом чате младше вашей должности.',
      target: '[data-coach="people"]',
    },
    {
      title: 'Правила',
      body: 'Нажмите «Ещё». Там правила проекта и возврат к выбору панели.',
      target: '[data-coach="more"]',
    },
  ]
}

function visibleTarget(selector) {
  if (!selector || typeof document === 'undefined') return null
  const nodes = document.querySelectorAll(selector)
  for (const node of nodes) {
    const rect = node.getBoundingClientRect()
    if (rect.width > 8 && rect.height > 8) return node
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
    let frame = 0
    const measure = () => {
      const node = visibleTarget(step?.target)
      if (!node) {
        setBox(null)
        return
      }
      node.scrollIntoView({ block: 'nearest', inline: 'nearest' })
      const rect = node.getBoundingClientRect()
      const pad = 6
      setBox({
        top: Math.max(8, rect.top - pad),
        left: Math.max(8, rect.left - pad),
        width: Math.min(window.innerWidth - 16, rect.width + pad * 2),
        height: rect.height + pad * 2,
        low: rect.top > window.innerHeight * 0.46,
      })
    }
    frame = window.requestAnimationFrame(measure)
    window.addEventListener('resize', measure)
    return () => {
      window.cancelAnimationFrame(frame)
      window.removeEventListener('resize', measure)
    }
  }, [step, layoutKey])

  return (
    <div className={`firstrun${box?.low ? ' is-high' : ''}`} role="dialog" aria-modal="true" aria-labelledby="firstrun-title">
      {box && (
        <div
          className="firstrun-spot"
          style={{ top: box.top, left: box.left, width: box.width, height: box.height }}
        />
      )}
      <div className="firstrun-sheet">
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
