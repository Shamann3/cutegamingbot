import { useEffect, useRef, useState } from 'react'

const GATE_LINES = [
  [
    { at: 0.18, label: 'Канал связи' },
    { at: 0.4, label: 'Кто входит' },
    { at: 0.64, label: 'Два контура' },
    { at: 0.86, label: 'Двери' },
  ],
  [
    { at: 0.18, label: 'Линия уже жива' },
    { at: 0.4, label: 'Допуск на месте' },
    { at: 0.64, label: 'Сотрудник или группа' },
    { at: 0.86, label: 'Выбор входа' },
  ],
  [
    { at: 0.18, label: 'Повторная сверка' },
    { at: 0.4, label: 'Сессия узнана' },
    { at: 0.64, label: 'Контур не сброшен' },
    { at: 0.86, label: 'Можно входить' },
  ],
]

const STAFF_LINES = [
  [
    { at: 0.28, label: 'Панель сотрудника' },
    { at: 0.62, label: 'Разделы должности' },
    { at: 0.9, label: 'Допуск' },
  ],
  [
    { at: 0.28, label: 'Сотрудник узнан' },
    { at: 0.62, label: 'Открыты только его разделы' },
    { at: 0.9, label: 'Банфулл отдельно' },
  ],
]

const GROUP_LINES = [
  [
    { at: 0.28, label: 'Панель администраторов групп' },
    { at: 0.62, label: 'Чат и должность' },
    { at: 0.9, label: 'Младших можно наказать' },
  ],
  [
    { at: 0.28, label: 'Группа узнана' },
    { at: 0.62, label: 'Права этого чата' },
    { at: 0.9, label: 'Старших система не пропустит' },
  ],
]

function nextTurn(kind) {
  const key = `epsilon.boot.${kind}`
  let turn = 0
  try {
    turn = Number(sessionStorage.getItem(key) || 0)
    sessionStorage.setItem(key, String(turn + 1))
  } catch {
    turn = 0
  }
  return Number.isFinite(turn) ? turn : 0
}

export function bootScript(kind) {
  const turn = nextTurn(kind)
  if (kind === 'staff') {
    const steps = STAFF_LINES[turn % STAFF_LINES.length]
    return { title: turn % 2 === 0 ? 'Контур сотрудника' : 'Повторный допуск', steps, duration: 1100 }
  }
  if (kind === 'group') {
    const steps = GROUP_LINES[turn % GROUP_LINES.length]
    return { title: turn % 2 === 0 ? 'Контур группы' : 'Чат на месте', steps, duration: 1100 }
  }
  const steps = GATE_LINES[turn % GATE_LINES.length]
  const titles = ['Сверка контура', 'Вход уже знакомый', 'Контур держится']
  return { title: titles[turn % titles.length], steps, duration: 2400 }
}

export default function SecurityBoot({
  personal = false,
  kind = 'gate',
  onDone,
}) {
  const scriptRef = useRef(null)
  if (!scriptRef.current) scriptRef.current = bootScript(kind)
  const script = scriptRef.current
  const [progress, setProgress] = useState(0)
  const [reduce, setReduce] = useState(false)
  const onDoneRef = useRef(onDone)
  const fired = useRef(false)
  onDoneRef.current = onDone

  const finish = () => {
    if (fired.current) return
    fired.current = true
    onDoneRef.current?.()
  }

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const still = media.matches
    setReduce(still)
    const backup = window.setTimeout(finish, 8000)
    if (still) {
      setProgress(1)
      const timer = window.setTimeout(finish, 420)
      return () => {
        window.clearTimeout(timer)
        window.clearTimeout(backup)
      }
    }

    const start = performance.now()
    let frame = 0
    let hold = 0
    const tick = (now) => {
      const value = Math.min(1, (now - start) / script.duration)
      setProgress(value)
      if (value < 1) {
        frame = window.requestAnimationFrame(tick)
        return
      }
      hold = window.setTimeout(finish, 180)
    }
    frame = window.requestAnimationFrame(tick)
    return () => {
      window.cancelAnimationFrame(frame)
      window.clearTimeout(hold)
      window.clearTimeout(backup)
    }
  }, [script.duration])

  const pct = Math.round(progress * 100)

  return (
    <div
      className={`boot${personal ? ' is-personal' : ''}${reduce ? ' is-still' : ''}`}
      role="button"
      tabIndex={0}
      onClick={finish}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          finish()
        }
      }}
    >
      <span className="boot-sweep" aria-hidden="true" />
      <span className="boot-corner boot-corner-tl" aria-hidden="true" />
      <span className="boot-corner boot-corner-tr" aria-hidden="true" />
      <span className="boot-corner boot-corner-bl" aria-hidden="true" />
      <span className="boot-corner boot-corner-br" aria-hidden="true" />

      <div className="boot-stage">
        <p className="boot-title">{script.title}</p>
        <p className="boot-pct" aria-hidden="true">{pct}</p>
        <div className="boot-track" aria-hidden="true">
          <div className="boot-fill" style={{ transform: `scaleX(${progress})` }} />
        </div>
        <ol className="boot-log">
          {script.steps.map((step, index) => {
            const on = progress + 0.001 >= step.at
            return (
              <li key={step.label} className={on ? 'is-on' : ''}>
                <span>{String(index + 1).padStart(2, '0')}</span>
                <span>{step.label}</span>
                <span>{on ? 'ок' : '···'}</span>
              </li>
            )
          })}
        </ol>
        <p className="boot-live" role="status">Сверка {pct} из 100</p>
      </div>
      <span className="boot-skip">Нажмите, чтобы войти сразу</span>
    </div>
  )
}
