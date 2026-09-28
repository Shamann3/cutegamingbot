import { useEffect, useRef, useState } from 'react'
import MatrixRain from './MatrixRain'
import { waitForDashboardStats } from '../lib/dashboardPrefetch'
import { bootIsComplete, bootProgressFrame } from '../lib/bootProgress'

/** Дольше этого экран статистику не ждёт — панель сама доберёт её поллингом. */
export const STATS_WAIT_CAP_MS = 6000

const DATA_STEP_LABEL = 'Статистика главной'

const DATA_STATE_TEXT = {
  loading: 'загрузка',
  ready: 'готово',
  later: 'догрузим',
}

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
    { at: 0.86, label: 'Права на месте' },
  ],
  [
    { at: 0.28, label: 'Вас узнали' },
    { at: 0.62, label: 'Закрытые страницы не показываем' },
    { at: 0.86, label: 'Доступ подтверждён' },
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
  // Панель сотрудника открывается сразу на главной — её цифры грузим здесь.
  const needsData = kind === 'staff'
  if (code) {
    return { title: 'Идёт проверка', steps: CODE_LINES, duration: 1800, code: true, needsData }
  }
  if (kind === 'staff') {
    const steps = STAFF_LINES[turn % STAFF_LINES.length]
    return { title: 'Открываем панель сотрудника', steps, duration: 1600, code: false, needsData }
  }
  if (kind === 'group') {
    const steps = GROUP_LINES[turn % GROUP_LINES.length]
    return { title: 'Открываем панель группы', steps, duration: 1400, code: false, needsData }
  }
  const steps = GATE_LINES[turn % GATE_LINES.length]
  return { title: turn % 2 === 0 ? 'Проверяем вход' : 'Вас узнали', steps, duration: 1600, code: false, needsData }
}

function detectStill() {
  if (typeof window === 'undefined') return true
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return true
  return false
}

function detectCalm() {
  if (detectStill()) return true
  try {
    if (localStorage.getItem('cf_admin_perf') === '1') return true
  } catch { /* ignore */ }
  return (navigator.hardwareConcurrency || 4) <= 2
}

/**
 * Экран перехода в панель. Пропустить его нельзя: он заканчивается, когда
 * полоса дошла до конца, а для панели сотрудника — ещё и когда статистика
 * главной уже в памяти (не дольше STATS_WAIT_CAP_MS).
 */
export default function SecurityBoot({
  personal = false,
  kind = 'gate',
  onDone,
}) {
  const scriptRef = useRef(null)
  if (!scriptRef.current) scriptRef.current = bootScript(kind)
  const script = scriptRef.current
  const [progress, setProgress] = useState(0)
  const [still] = useState(detectStill)
  const [calm] = useState(detectCalm)
  const [dataState, setDataState] = useState(script.needsData ? 'loading' : 'ready')
  const dataReady = dataState !== 'loading'
  const dataReadyRef = useRef(!script.needsData)
  const onDoneRef = useRef(onDone)
  const fired = useRef(false)
  onDoneRef.current = onDone

  const finish = () => {
    if (fired.current) return
    fired.current = true
    onDoneRef.current?.()
  }

  useEffect(() => {
    if (!script.needsData) return undefined
    let alive = true
    waitForDashboardStats(STATS_WAIT_CAP_MS).then((snapshot) => {
      if (!alive) return
      dataReadyRef.current = true
      setDataState(snapshot ? 'ready' : 'later')
    })
    return () => {
      alive = false
    }
  }, [script.needsData])

  useEffect(() => {
    if (!still) return undefined
    setProgress(dataReady ? 1 : 0.5)
    if (!dataReady) return undefined
    const timer = window.setTimeout(finish, 260)
    return () => window.clearTimeout(timer)
  }, [still, dataReady])

  useEffect(() => {
    if (still) return undefined
    // Страховка на случай, если rAF заморожен (вкладка в фоне и т.п.).
    const backup = window.setTimeout(finish, script.duration + STATS_WAIT_CAP_MS + 2000)

    const start = performance.now()
    let frame = 0
    let hold = 0
    let value = 0
    let readyAt = null
    let readyFrom = 0
    const tick = (now) => {
      const elapsed = now - start
      if (dataReadyRef.current && readyAt == null) {
        readyAt = elapsed
        readyFrom = value
      }
      value = bootProgressFrame({
        elapsed,
        duration: script.duration,
        needsData: script.needsData,
        readyAt,
        readyFrom,
      })
      setProgress(value)
      if (bootIsComplete(value)) {
        setProgress(1)
        hold = window.setTimeout(finish, 180)
        return
      }
      frame = window.requestAnimationFrame(tick)
    }
    frame = window.requestAnimationFrame(tick)
    return () => {
      window.cancelAnimationFrame(frame)
      window.clearTimeout(hold)
      window.clearTimeout(backup)
    }
  }, [still, script.duration, script.needsData])

  const pct = Math.round(progress * 100)

  return (
    <div
      className={`boot${personal ? ' is-personal' : ''}${still ? ' is-still' : ''}`}
      role="status"
      aria-live="polite"
      aria-busy={pct < 100}
    >
      <MatrixRain className="boot-matrix" paused={calm} prewarm={40} />
      <span className="boot-veil" aria-hidden="true" />
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
          {script.needsData && (
            <li
              className={`boot-log-data${dataReady ? ' is-on' : ' is-loading'}`}
              data-state={dataState}
            >
              <span>{DATA_STEP_LABEL}</span>
              <span>{DATA_STATE_TEXT[dataState]}</span>
            </li>
          )}
        </ol>
        <p className="boot-live">{script.code ? 'Пишем проверку' : 'Проверка'} {pct} из 100</p>
      </div>
    </div>
  )
}
