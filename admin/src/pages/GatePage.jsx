import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchAdminAuthStatus } from '../lib/adminClient'
import { accentIsPersonal, applyAccentToDocument, loadStoredAccent, persistAccent } from '../lib/accentTheme'
import { portraitFrom } from '../lib/gateRecovery'
import EpsilonLogo from '../components/EpsilonLogo'
import AccentPalette from '../components/AccentPalette'
import MatrixRain from '../components/MatrixRain'
import { useOutsideDismiss } from '../lib/outsideDismiss'
import { usePerfMode } from '../lib/perfMode'

/** Доступ ещё не сверен — двери уже видны и кликабельны. */
const GUEST_PORTRAIT = portraitFrom(null)

/** Слабое устройство или системный покой — дождь не считаем совсем. */
function detectStillGate() {
  if (typeof window === 'undefined') return true
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return true
  return (navigator.hardwareConcurrency || 4) <= 2
}

function Door({ title, detail, mark, open, onClick, order = 0 }) {
  return (
    <button
      type="button"
      className={`gate-door gate-rise${open ? ' is-open' : ' is-sealed'}`}
      style={{ '--rise': order }}
      onClick={onClick}
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
  const [hold, setHold] = useState(false)
  const [still] = useState(detectStillGate)
  const { lightMode, setLightMode } = usePerfMode()
  const sparse = lightMode && !still
  const requestId = useRef(0)
  const paletteRef = useRef(null)

  const load = useCallback(() => {
    const id = requestId.current + 1
    requestId.current = id
    setChecking(true)
    setError('')
    fetchAdminAuthStatus()
      .then((status) => {
        if (requestId.current !== id) return
        setPortrait(portraitFrom(status))
      })
      .catch((err) => {
        if (requestId.current !== id) return
        // Двери остаются с гостевым портретом — не прячем карточки.
        setPortrait(GUEST_PORTRAIT)
        setError(err.message || 'Не удалось сверить доступ')
      })
      .finally(() => {
        if (requestId.current === id) setChecking(false)
      })
  }, [])

  useEffect(() => load(), [load])

  // Палитра закрывается по тапу мимо неё и по Escape — как в панели Эпсилона.
  // Тап, которым её закрыли, не нажимает дверь под пальцем.
  useOutsideDismiss(colorOpen, [paletteRef], () => setColorOpen(false))

  const staffDetail = portrait.staffCanEnter
    ? 'Команда проекта. Нажмите, чтобы войти.'
    : portrait.applicationStatus === 'pending'
      ? 'Заявка уже отправлена. Ждём решение.'
      : 'Вы ещё не в команде. Нажмите — откроется заявка.'

  const groupDetail = portrait.groupCanEnter
    ? <>Дальше нужен ключ кабинета <CuteBrand />.</>
    : <>Кабинета ещё нет. Нажмите — откроется заявка в <CuteBrand />.</>

  const pressStaff = () => {
    if (portrait.staffCanEnter) {
      onStaffEnter()
      return
    }
    if (portrait.applicationStatus === 'pending') {
      setHold(true)
      return
    }
    onStaffApply()
  }

  const pressGroup = () => {
    if (portrait.groupCanEnter) onGroupEnter(portrait)
    else onGroupApply()
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

        {hold ? (
          <div className="gate-hold" role="status">
            <h2 className="gate-title">Заявка уже у создателя</h2>
            <p className="gate-lead">Вход откроется после одобрения. Повторно отправлять её не нужно.</p>
            <button type="button" className="gate-text" onClick={() => setHold(false)}>К выбору панели</button>
          </div>
        ) : (
          <div className="gate-doors" aria-busy={checking || undefined}>
            <Door
              title="Панель сотрудника"
              detail={error ? 'Ключ, затем код из приложения.' : staffDetail}
              mark={portrait.applicationStatus === 'pending' && !error ? 'Ждёт' : portrait.staffCanEnter || error ? 'Войти' : 'Заявка'}
              open={portrait.staffCanEnter || Boolean(error)}
              onClick={error ? onStaffEnter : pressStaff}
              order={4}
            />
            <Door
              title="Панель администратора"
              detail={portrait.groupCanEnter ? groupDetail : <>Кабинета ещё нет. Нажмите — откроется заявка в <CuteBrand />.</>}
              mark={portrait.groupCanEnter ? 'Войти' : 'Заявка'}
              open
              onClick={pressGroup}
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
