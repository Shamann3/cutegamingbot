import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchAdminAuthStatus } from '../lib/adminClient'
import { accentIsPersonal, applyAccentToDocument, loadStoredAccent, persistAccent } from '../lib/accentTheme'
import { portraitFrom } from '../lib/gateRecovery'
import EpsilonLogo from '../components/EpsilonLogo'
import AccentPalette from '../components/AccentPalette'
import MatrixRain from '../components/MatrixRain'

/** Доступ ещё не сверен — двери уже видны и кликабельны. */
const GUEST_PORTRAIT = portraitFrom(null)

/** Слабое устройство или запрошен покой — фон без анимации. */
function detectCalmGate() {
  if (typeof window === 'undefined') return true
  try {
    if (localStorage.getItem('cf_admin_perf') === '1') return true
  } catch { /* ignore */ }
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return true
  return (navigator.hardwareConcurrency || 4) <= 2
}

function Door({ title, detail, open, onClick, order = 0 }) {
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
      <span className="gate-door-mark">{open ? 'Войти' : 'Закрыто'}</span>
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
  const [calm] = useState(detectCalmGate)
  const requestId = useRef(0)

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

  const staffDetail = portrait.staffCanEnter
    ? 'Сюда заходят сотрудники Эпсилона. Для модерации нашего проекта'
    : portrait.applicationStatus === 'pending'
      ? 'Сюда заходят сотрудники Эпсилона. Заявка уже у создателя, повторно отправлять не нужно.'
      : 'Сюда заходят сотрудники Эпсилона. Для модерации нашего проекта. Нажатие откроет заявку.'

  const groupDetail = portrait.groupCanEnter
    ? <>Эта кнопка предназначается для администраторов официальных групп нашего проекта <CuteBrand /></>
    : <>Эта кнопка предназначается для администраторов официальных групп нашего проекта <CuteBrand />. Нажатие откроет заявку.</>

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
      <MatrixRain className="gate-matrix" paused={calm} fps={16} />
      <div className="gate-veil" aria-hidden="true" />
      <div className="gate-frame" aria-hidden="true" />
      <div className={`gate-sheet${colorOpen ? ' is-color' : ''}`}>
        <header className="gate-head">
          <span className="gate-rise gate-logo-slot" style={{ '--rise': 0 }}>
            <EpsilonLogo size="sm" decorative />
          </span>
          <h1 className="gate-title gate-rise" style={{ '--rise': 1 }}>Куда вам нужно войти?</h1>
          <p className="gate-lead gate-rise" style={{ '--rise': 2 }}>Выберите один из вариантов</p>
          <p className="gate-lead gate-rise" style={{ '--rise': 3 }}>По желанию вы можете выбрать любой цвет интерфейса для приятной работы</p>
          <button
            type="button"
            className="gate-color-btn gate-rise"
            style={{ '--rise': 4 }}
            aria-expanded={colorOpen}
            onClick={() => setColorOpen((open) => !open)}
          >
            {colorOpen ? 'Скрыть палитру' : 'Изменить цвет интерфейса'}
          </button>
          {colorOpen && (
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
          )}
        </header>

        {error && (
          <div className="gate-recover" role="alert">
            <p className="gate-status gate-status-error">{error}</p>
            <p className="gate-lead">Сверка не прошла — двери всё равно доступны. Можно повторить или войти вручную.</p>
            <div className="gate-recover-actions">
              <button type="button" className="firstrun-next" onClick={load}>Повторить сверку</button>
              <button type="button" className="gate-text" onClick={onStaffEnter}>Панель сотрудника</button>
              <button type="button" className="gate-text" onClick={onStaffApply}>Заявка в команду</button>
              <button type="button" className="gate-text" onClick={onGroupApply}>Заявка в группу</button>
            </div>
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
              detail={staffDetail}
              open={portrait.staffCanEnter}
              onClick={pressStaff}
              order={5}
            />
            <Door
              title="Панель администратора"
              detail={groupDetail}
              open={portrait.groupCanEnter}
              onClick={pressGroup}
              order={6}
            />
          </div>
        )}
      </div>
    </div>
  )
}
