import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchAdminAuthStatus } from '../lib/adminClient'
import { accentIsPersonal, applyAccentToDocument, loadStoredAccent, persistAccent } from '../lib/accentTheme'
import { portraitFrom, rememberPortrait } from '../lib/gateRecovery'
import EpsilonLogo from '../components/EpsilonLogo'
import AccentPalette from '../components/AccentPalette'
import MatrixRain from '../components/MatrixRain'
import { useOutsideDismiss } from '../lib/outsideDismiss'
import { usePerfMode } from '../lib/perfMode'
import { playMeme } from '../lib/memeSounds'

/** Доступ ещё не сверен — двери уже видны и кликабельны. */
const GUEST_PORTRAIT = portraitFrom(null)

/** Слабое устройство или системный покой — дождь не считаем совсем. */
function detectStillGate() {
  if (typeof window === 'undefined') return true
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return true
  return (navigator.hardwareConcurrency || 4) <= 2
}

function Door({ title, detail, mark, open, onClick, order = 0, busy = false }) {
  return (
    <button
      type="button"
      className={`gate-door gate-rise${open ? ' is-open' : ' is-sealed'}`}
      style={{ '--rise': order }}
      onClick={onClick}
      disabled={busy}
      aria-busy={busy || undefined}
    >
      <span className="gate-door-sheen" aria-hidden="true" />
      <span className="gate-door-title">{title}</span>
      <span className="gate-door-detail">{detail}</span>
      <span className="gate-door-mark">{mark}</span>
    </button>
  )
}

function CuteBrand() {
  return <span className="gate-brand-word">CuteGamingBot</span>
}

export default function GatePage({ onStaffEnter, onStaffApply, onGroupEnter, onGroupApply }) {
  const [personal, setPersonal] = useState(() => accentIsPersonal(loadStoredAccent()))
  const [accent, setAccent] = useState(() => loadStoredAccent())
  const [colorOpen, setColorOpen] = useState(false)
  const [checking, setChecking] = useState(true)
  const [error, setError] = useState('')
  const [portrait, setPortrait] = useState(GUEST_PORTRAIT)
  const [hold, setHold] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [still] = useState(detectStillGate)
  const { lightMode, setLightMode } = usePerfMode()
  const sparse = lightMode && !still
  const requestId = useRef(0)
  const flight = useRef(Promise.resolve(GUEST_PORTRAIT))

  useEffect(() => {
    playMeme('gate')
  }, [])
  const paletteRef = useRef(null)

  const load = useCallback(() => {
    const id = requestId.current + 1
    requestId.current = id
    setChecking(true)
    setError('')
    const job = fetchAdminAuthStatus()
      .then((status) => {
        const face = portraitFrom(status)
        if (requestId.current !== id) return face
        setPortrait(face)
        rememberPortrait(face)
        return face
      })
      .catch((err) => {
        if (requestId.current === id) {
          // Двери остаются с гостевым портретом — не прячем карточки.
          setPortrait(GUEST_PORTRAIT)
          rememberPortrait(GUEST_PORTRAIT)
          setError(err.message || 'Не удалось сверить доступ')
        }
        return null
      })
      .finally(() => {
        if (requestId.current === id) setChecking(false)
      })
    flight.current = job
  }, [])

  useEffect(() => load(), [load])

  // Палитра закрывается по тапу мимо неё и по Escape — как в панели Эпсилона.
  // Тап, которым её закрыли, не нажимает дверь под пальцем.
  useOutsideDismiss(colorOpen, [paletteRef], () => setColorOpen(false))

  const staffKnown = portrait.isProjectCreator || portrait.staffCanEnter
  const staffDetail = checking && !staffKnown
    ? 'Сверяем, открыт ли вход.'
    : staffKnown
      ? 'Команда проекта. Нажмите, чтобы войти.'
      : portrait.applicationStatus === 'pending'
        ? 'Заявка уже отправлена. Ждём решение.'
        : 'Вы ещё не в команде. Нажмите — откроется заявка.'

  const groupDetail = checking && !portrait.isProjectCreator && !portrait.groupCanEnter
    ? 'Сверяем, открыт ли кабинет.'
    : portrait.isProjectCreator
      ? 'Кабинет групп. Нажмите — откроется сразу.'
      : portrait.groupCanEnter
        ? <>Дальше нужен ключ кабинета <CuteBrand />.</>
        : portrait.groupApplicationStatus === 'pending'
          ? 'Заявка уже у создателя. Ключ придёт после одобрения.'
          : portrait.groupHoldsSeat
            ? 'Должность уже есть. Ключ выдаётся только после заявки. Нажмите и отправьте её.'
            : <>Кабинета ещё нет. Нажмите — откроется заявка в <CuteBrand />.</>

  const pressStaff = async () => {
    if (busy) return
    setNote('')
    setBusy(true)
    try {
      let face = portrait
      if (checking) {
        try {
          face = await flight.current
        } catch {
          face = null
        }
        if (!face) {
          onStaffEnter()
          return
        }
      }
      if (!(face?.isProjectCreator || face?.staffCanEnter)) {
        if (face?.applicationStatus === 'pending') {
          setHold('staff')
          return
        }
        onStaffApply()
        return
      }
      try {
        await onStaffEnter(face)
      } catch (err) {
        setNote(err?.message || 'Панель не открылась. Нажмите ещё раз.')
      }
    } finally {
      setBusy(false)
    }
  }

  const pressGroup = async () => {
    if (busy) return
    setNote('')
    setBusy(true)
    try {
      let face = portrait
      if (checking) {
        try {
          face = await flight.current
        } catch {
          face = null
        }
        if (!face) {
          onGroupApply()
          return
        }
      }
      if (face?.isProjectCreator) {
        onGroupEnter(face)
        return
      }
      if (error || !face?.groupCanEnter) {
        if (!error && face?.groupApplicationStatus === 'pending') {
          setHold('group')
          return
        }
        onGroupApply()
        return
      }
      onGroupEnter(face)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={`gate-root gate-anim${personal ? ' is-personal' : ''}`}>
      <MatrixRain
        className="gate-matrix"
        paused={still}
        density={sparse ? 0.08 : 1}
        fps={sparse ? 10 : 28}
        prewarm={sparse ? 3 : 36}
      />
      <div className="gate-veil" aria-hidden="true" />
      <div className="gate-frame" aria-hidden="true" />
      <div className={`gate-sheet${colorOpen ? ' is-color' : ''}`}>
        <div className="gate-stage">
        <header className="gate-head">
          <span className="gate-rise gate-logo-slot" style={{ '--rise': 0 }}>
            <EpsilonLogo size="sm" decorative />
          </span>
          <h1 className="gate-title gate-rise" style={{ '--rise': 1 }}>Куда вам нужно войти?</h1>
          <p className="gate-lead gate-rise" style={{ '--rise': 2 }}>Одна дверь: сотрудник проекта или администратор группы.</p>
        </header>

        {error && (
          <div className="gate-recover gate-rise" style={{ '--rise': 3 }} role="alert">
            <p className="gate-status gate-status-error">Сервер не ответил. Ниже можно войти по ключу.</p>
            <p className="gate-lead">{error}</p>
            <button type="button" className="gate-text" onClick={load}>Повторить сверку</button>
          </div>
        )}

        {note && !hold && (
          <p className="gate-status gate-status-error" role="alert">{note}</p>
        )}

        {hold ? (
          <div className="gate-hold" role="status">
            <h2 className="gate-title">Заявка уже у создателя</h2>
            <p className="gate-lead">
              {hold === 'group'
                ? 'Ключ придёт после одобрения. Повторно отправлять заявку не нужно.'
                : 'Вход откроется после одобрения. Повторно отправлять её не нужно.'}
            </p>
            <button type="button" className="gate-text" onClick={() => setHold('')}>К выбору панели</button>
          </div>
        ) : (
          <div className="gate-doors" aria-busy={checking || undefined}>
            <Door
              title="Панель сотрудника"
              detail={error ? 'Ключ, затем код из приложения.' : staffDetail}
              mark={checking && !staffKnown && !error ? '…' : portrait.applicationStatus === 'pending' && !error && !portrait.isProjectCreator ? 'Ждёт' : staffKnown || error ? 'Войти' : 'Заявка'}
              open={staffKnown || Boolean(error)}
              onClick={error ? onStaffEnter : pressStaff}
              busy={busy}
              order={4}
            />
            <Door
              title="Панель администратора"
              detail={groupDetail}
              mark={checking && !portrait.isProjectCreator && !portrait.groupCanEnter ? '…' : portrait.groupCanEnter || portrait.isProjectCreator ? 'Войти' : !error && portrait.groupApplicationStatus === 'pending' ? 'Ждёт' : 'Заявка'}
              open
              onClick={pressGroup}
              busy={busy}
              order={5}
            />
          </div>
        )}

        <div className="gate-palette-slot gate-rise" style={{ '--rise': 6 }} ref={paletteRef}>
          <div className="gate-tools">
            <button
              type="button"
              className="gate-color-btn"
              aria-expanded={colorOpen}
              onClick={() => setColorOpen((open) => !open)}
            >
              {colorOpen ? 'Скрыть палитру' : 'Цвет и прозрачность'}
            </button>
            <button
              type="button"
              className={`gate-color-btn gate-perf-btn${lightMode ? ' is-on' : ''}`}
              aria-pressed={lightMode}
              onClick={() => setLightMode(!lightMode)}
            >
              {lightMode ? 'Обычный режим' : 'Оптимизировать'}
            </button>
          </div>
          {colorOpen && (
            <div className="gate-palette-pop">
              <AccentPalette
                inline
                value={accent}
                onChange={(next) => {
                  const saved = persistAccent(next)
                  applyAccentToDocument(saved, { flash: true })
                  setAccent(saved)
                  setPersonal(accentIsPersonal(saved))
                }}
              />
            </div>
          )}
        </div>
        </div>
      </div>
    </div>
  )
}
