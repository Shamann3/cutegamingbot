import { useEffect, useRef, useState } from 'react'

const GATE_LINES = [
  [
    { at: 0.18, label: 'Проверяем связь' },
    { at: 0.4, label: 'Смотрим, кто вошёл' },
    { at: 0.64, label: 'Две панели: сотрудник и группа' },
    { at: 0.86, label: 'Сейчас будет выбор' },
  ],
  [
    { at: 0.18, label: 'Вы уже входили' },
    { at: 0.4, label: 'Доступ на месте' },
    { at: 0.64, label: 'Сотрудник или группа' },
    { at: 0.86, label: 'Можно выбирать' },
  ],
]

const CODE_LINES = [
  { at: 0.16, label: 'кто_вошёл()' },
  { at: 0.4, label: 'если сотрудник: открыть его страницы' },
  { at: 0.66, label: 'если группа: открыть только этот чат' },
  { at: 0.88, label: 'проверка закончена' },
]

const STAFF_LINES = [
  [
    { at: 0.28, label: 'Открываем панель сотрудника' },
    { at: 0.62, label: 'Страницы вашей должности' },
    { at: 0.9, label: 'Готово' },
  ],
  [
    { at: 0.28, label: 'Вас узнали' },
    { at: 0.62, label: 'Закрытые страницы не показываем' },
    { at: 0.9, label: 'Готово' },
  ],
]

const GROUP_LINES = [
  [
    { at: 0.28, label: 'Открываем панель группы' },
    { at: 0.62, label: 'Чат и ваша должность' },
    { at: 0.9, label: 'Младших можно наказать' },
  ],
  [
    { at: 0.28, label: 'Группа узнана' },
    { at: 0.62, label: 'Права только этого чата' },
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
  const code = turn % 3 === 2
  if (code) {
    return { title: 'Идёт проверка', steps: CODE_LINES, duration: 1700, code: true }
  }
  if (kind === 'staff') {
    const steps = STAFF_LINES[turn % STAFF_LINES.length]
    return { title: 'Открываем панель сотрудника', steps, duration: 1100, code: false }
  }
  if (kind === 'group') {
    const steps = GROUP_LINES[turn % GROUP_LINES.length]
    return { title: 'Открываем панель группы', steps, duration: 1100, code: false }
  }
  const steps = GATE_LINES[turn % GATE_LINES.length]
  return { title: turn % 2 === 0 ? 'Проверяем вход' : 'Вас узнали', steps, duration: 1600, code: false }
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
        <ol className={script.code ? 'boot-log boot-code' : 'boot-log'}>
          {script.steps.map((step) => {
            const on = progress + 0.001 >= step.at
            return (
              <li key={step.label} className={on ? 'is-on' : ''}>
                <span>{step.label}</span>
                <span>{on ? 'готово' : 'ждём'}</span>
              </li>
            )
          })}
        </ol>
        <p className="boot-live" role="status">{script.code ? 'Пишем проверку' : 'Проверка'} {pct} из 100</p>
      </div>
      <span className="boot-skip">Нажмите, чтобы войти сразу</span>
    </div>
  )
}
