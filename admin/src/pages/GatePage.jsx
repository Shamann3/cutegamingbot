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
import { gateFlowMs } from './sections/GroupEnter'
import AcceptedPass from '../components/AcceptedPass'

/** Доступ ещё не сверен — двери уже видны и кликабельны. */
const GUEST_PORTRAIT = portraitFrom(null)

/** Слабое устройство или системный покой — дождь не считаем совсем. */
function detectStillGate() {
  if (typeof window === 'undefined') return true
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return true
  return (navigator.hardwareConcurrency || 4) <= 2
}

function Door({ title, detail, mark, open, onClick, order = 0, busy = false, chosen = false }) {
  return (
    <button
      type="button"
      className={`gate-door gate-rise${open ? ' is-open' : ' is-sealed'}${chosen ? ' is-chosen' : ''}`}
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
  const [pass, setPass] = useState('')
  const watched = useRef({ staff: false, group: false })
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [flow, setFlow] = useState('')
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

  useEffect(() => {
    if (portrait.applicationStatus === 'pending') watched.current.staff = true
    if (portrait.groupApplicationStatus === 'pending') watched.current.group = true
  }, [portrait.applicationStatus, portrait.groupApplicationStatus])

  useEffect(() => {
    const live = portrait.applicationStatus === 'pending'
      || portrait.groupApplicationStatus === 'pending'
      || Boolean(hold)
    if (!live || pass) return undefined
    const timer = window.setInterval(async () => {
      try {
        const status = await fetchAdminAuthStatus()
        const face = portraitFrom(status)
        setPortrait(face)
        rememberPortrait(face)
        setChecking(false)
        if (watched.current.staff && face.staffCanEnter) setPass('staff')
        else if (watched.current.group && face.groupCanEnter && !face.isProjectCreator) setPass('group')
        else if (watched.current.staff && face.applicationStatus === 'rejected') setPass('staff-no')
        else if (watched.current.group && face.groupApplicationStatus === 'rejected') setPass('group-no')
      } catch {
        // дверь остаётся, сверка повторится
      }
    }, 4000)
    return () => window.clearInterval(timer)
  }, [portrait.applicationStatus, portrait.groupApplicationStatus, hold, pass])

  // Палитра закрывается по тапу мимо неё и по Escape — как в панели Эпсилона.
  // Тап, которым её закрыли, не нажимает дверь под пальцем.
  useOutsideDismiss(colorOpen, [paletteRef], () => setColorOpen(false))

  const staffKnown = portrait.isProjectCreator || portrait.staffCanEnter
  const staffDetail = checking && !staffKnown
    ? 'Сверяем, открыт ли вход.'
    : staffKnown
      ? 'Вы уже в команде. Нажмите: ключ, затем шесть цифр из приложения.'
      : portrait.applicationStatus === 'pending'
        ? 'Заявка уже отправлена. Когда её примут, вход откроется здесь.'
        : 'Для команды проекта. Ключ выдаёт создатель. Нажмите — откроется регистрация.'

  const groupDetail = checking && !portrait.isProjectCreator && !portrait.groupCanEnter
    ? 'Сверяем, открыт ли кабинет.'
    : portrait.isProjectCreator
      ? 'Кабинет групп. Нажмите — откроется сразу, без ключа.'
      : portrait.groupCanEnter
        ? 'Вставьте ключ из сообщения бота, затем шесть цифр из приложения.'
        : portrait.groupApplicationStatus === 'pending'
          ? 'Заявка уже у создателя. Ключ придёт в бота, когда её примут.'
          : portrait.groupHoldsSeat
            ? 'Должность уже есть. Сначала отправьте заявку — ключ придёт в бота.'
            : <>Для администратора группы. Нажмите — заявка. Ключ придёт в бота <CuteBrand />.</>

  const sail = async (kind) => {
    const ms = gateFlowMs()
    if (!ms) return
    setFlow(kind)
    await new Promise((resolve) => window.setTimeout(resolve, ms))
  }

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
        await sail('staff')
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
        await sail('group')
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
      await sail('group')
      onGroupEnter(face)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={`gate-root gate-anim${personal ? ' is-personal' : ''}${flow ? ' is-flow' : ''}`}>
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
          <p className="gate-lead gate-rise" style={{ '--rise': 2 }}>Сотрудник проекта — «Панель сотрудника». Администратор группы — «Панель администратора».</p>
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

        {pass === 'staff' || pass === 'group' ? (
          <AcceptedPass
            kind={pass}
            onAction={() => (pass === 'group' ? onGroupEnter(portrait) : onStaffEnter(portrait))}
          />
        ) : pass === 'staff-no' || pass === 'group-no' ? (
          <div className="accept-pass" role="status">
            <h2 className="accept-title">Заявку не приняли</h2>
            <p className="gate-lead">
              {pass === 'group-no'
                ? 'В эту группу снова можно через 7 дней.'
                : 'Панель сотрудника по этой заявке не откроется.'}
            </p>
            <button type="button" className="auth-btn auth-btn-primary" onClick={() => setPass('')}>
              К выбору панели
            </button>
          </div>
        ) : hold ? (
          <div className="gate-hold" role="status">
            <h2 className="gate-title">Заявка уже у создателя</h2>
            <p className="gate-lead">
              {hold === 'group'
                ? 'Повторно отправлять заявку не нужно. Когда создатель её примет, бот пришлёт «Заявка принята». Нажмите на ключ в том сообщении, скопируйте его и снова откройте «Панель администратора».'
                : 'Повторно отправлять заявку не нужно. Когда создатель её примет, откройте «Панель сотрудника», вкладку «Вход», и введите тот же ключ и шесть цифр из приложения.'}
            </p>
            <button type="button" className="gate-text" onClick={() => setHold('')}>К выбору панели</button>
          </div>
        ) : (
          <div className="gate-doors" aria-busy={checking || undefined}>
            <Door
              title="Панель сотрудника"
              detail={error ? 'Ключ, затем код из приложения.' : staffDetail}
              mark={checking && !staffKnown && !error ? '…' : portrait.applicationStatus === 'pending' && !error && !portrait.isProjectCreator ? 'Ждёт' : staffKnown || error ? 'Войти' : 'Регистрация'}
              open={staffKnown || Boolean(error)}
              onClick={error ? onStaffEnter : pressStaff}
              busy={busy}
              chosen={flow === 'staff'}
              order={4}
            />
            <Door
              title="Панель администратора"
              detail={groupDetail}
              mark={checking && !portrait.isProjectCreator && !portrait.groupCanEnter ? '…' : portrait.groupCanEnter || portrait.isProjectCreator ? 'Войти' : !error && portrait.groupApplicationStatus === 'pending' ? 'Ждёт' : 'Заявка'}
              open
              onClick={pressGroup}
              busy={busy}
              chosen={flow === 'group'}
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
