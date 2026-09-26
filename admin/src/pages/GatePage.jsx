import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { fetchAdminAuthStatus } from '../lib/adminClient'
import { accentIsPersonal, applyAccentToDocument, loadStoredAccent, persistAccent } from '../lib/accentTheme'
import { portraitFrom } from '../lib/gateRecovery'
import EpsilonLogo from '../components/EpsilonLogo'
import AccentPalette from '../components/AccentPalette'

function Door({ title, detail, open, busy, disabled, onClick }) {
  const stateClass = open ? 'is-open' : 'is-sealed'
  return (
    <button
      type="button"
      className={`gate-door ${stateClass}${busy ? ' is-busy' : ''}`}
      onClick={onClick}
      disabled={disabled}
      aria-busy={busy || undefined}
    >
      <span className="gate-door-title">{title}</span>
      <span className="gate-door-detail">{detail}</span>
      <span className="gate-door-mark">
        {busy ? 'Проверка…' : open ? 'Войти' : 'Закрыто'}
      </span>
    </button>
  )
}

export default function GatePage({ onStaffEnter, onStaffApply, onGroupEnter, onGroupApply }) {
  const [personal, setPersonal] = useState(() => accentIsPersonal(loadStoredAccent()))
  const [accent, setAccent] = useState(() => loadStoredAccent())
  const [colorOpen, setColorOpen] = useState(false)

  // phase: 'loading' | 'ready' | 'error'
  const [phase, setPhase] = useState('loading')
  const [error, setError] = useState('')
  const [portrait, setPortrait] = useState(null)
  const [hold, setHold] = useState(false)
  // 'staff' | 'group' | null — защита от двойного клика во время перехода
  const [pendingAction, setPendingAction] = useState(null)

  const requestId = useRef(0)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      // инвалидируем любой незавершённый запрос
      requestId.current += 1
    }
  }, [])

  const load = useCallback(() => {
    const id = ++requestId.current
    setPhase('loading')
    setError('')
    setHold(false)
    setPendingAction(null)

    fetchAdminAuthStatus()
      .then((status) => {
        if (!mountedRef.current || requestId.current !== id) return
        setPortrait(portraitFrom(status))
        setPhase('ready')
      })
      .catch((err) => {
        if (!mountedRef.current || requestId.current !== id) return
        setPortrait(null)
        setError(err?.message || 'Не удалось сверить доступ')
        setPhase('error')
      })
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const handleAccentChange = useCallback((next) => {
    const saved = persistAccent(next)
    applyAccentToDocument(saved)
    setAccent(saved)
    setPersonal(accentIsPersonal(saved))
  }, [])

  const staffCanEnter = Boolean(portrait?.staffCanEnter)
  const groupCanEnter = Boolean(portrait?.groupCanEnter)
  const staffPending = portrait?.applicationStatus === 'pending'

  const staffDetail = useMemo(() => {
    if (staffCanEnter) {
      return 'Сюда заходят сотрудники Эпсилона. Для модерации нашего проекта'
    }
    if (staffPending) {
      return 'Сюда заходят сотрудники Эпсилона. Заявка уже у создателя, повторно отправлять не нужно.'
    }
    return 'Сюда заходят сотрудники Эпсилона. Для модерации нашего проекта. Нажатие откроет заявку.'
  }, [staffCanEnter, staffPending])

  const groupDetail = useMemo(() => {
    if (groupCanEnter) {
      return 'Эта кнопка предназначается для администраторов официальных групп нашего проекта CuteGamingBot'
    }
    return 'Эта кнопка предназначается для администраторов официальных групп нашего проекта CuteGamingBot. Нажатие откроет заявку.'
  }, [groupCanEnter])

  const pressStaff = useCallback(() => {
    if (phase !== 'ready' || !portrait || pendingAction) return

    if (staffCanEnter) {
      setPendingAction('staff')
      onStaffEnter?.()
      return
    }

    if (staffPending) {
      setHold(true)
      return
    }

    setPendingAction('staff')
    onStaffApply?.()
  }, [phase, portrait, pendingAction, staffCanEnter, staffPending, onStaffEnter, onStaffApply])

  const pressGroup = useCallback(() => {
    if (phase !== 'ready' || !portrait || pendingAction) return

    setPendingAction('group')
    if (groupCanEnter) {
      onGroupEnter?.(portrait)
    } else {
      onGroupApply?.()
    }
  }, [phase, portrait, pendingAction, groupCanEnter, onGroupEnter, onGroupApply])

  const showDoors = phase !== 'error' && !hold
  const doorsDisabled = phase !== 'ready' || pendingAction !== null

  return (
    <div className={`gate-root${personal ? ' is-personal' : ''}`}>
      <div className="gate-frame" aria-hidden="true" />
      <div className={`gate-sheet${colorOpen ? ' is-color' : ''}`}>
        <header className="gate-head">
          <EpsilonLogo size="sm" decorative />
          <h1 className="gate-title">Куда вам нужно войти?</h1>
          <p className="gate-lead">Выберите один из вариантов</p>
          <p className="gate-lead">
            По желанию вы можете выбрать любой цвет интерфейса для приятной работы
          </p>
          <button
            type="button"
            className="gate-color-btn"
            aria-expanded={colorOpen}
            aria-controls="gate-color-panel"
            onClick={() => setColorOpen((open) => !open)}
          >
            {colorOpen ? 'Скрыть палитру' : 'Изменить цвет интерфейса'}
          </button>
          {colorOpen && (
            <div id="gate-color-panel" className="gate-color-panel">
              <AccentPalette inline value={accent} onChange={handleAccentChange} />
            </div>
          )}
        </header>

        {phase === 'loading' && (
          <div className="realm-load" role="status">
            <span />
            <p>Сверка допуска</p>
          </div>
        )}

        {phase === 'error' && (
          <div className="gate-recover" role="alert">
            <p className="gate-status gate-status-error">{error}</p>
            <p className="gate-lead">
              Проверка не прошла. Панель можно открыть вручную: если доступа нет, она вернёт к выбору.
            </p>
            <div className="gate-recover-actions">
              <button type="button" className="firstrun-next" onClick={load}>
                Повторить сверку
              </button>
              <button
                type="button"
                className="gate-text"
                onClick={() => onStaffEnter?.()}
              >
                Панель сотрудника
              </button>
              <button
                type="button"
                className="gate-text"
                onClick={() => onStaffApply?.()}
              >
                Заявка в команду
              </button>
              <button
                type="button"
                className="gate-text"
                onClick={() => onGroupApply?.()}
              >
                Заявка в группу
              </button>
            </div>
          </div>
        )}

        {hold && phase !== 'error' && (
          <div className="gate-hold" role="status">
            <h2 className="gate-title">Заявка уже у создателя</h2>
            <p className="gate-lead">
              Вход откроется после одобрения. Повторно отправлять её не нужно.
            </p>
            <button
              type="button"
              className="gate-text"
              onClick={() => setHold(false)}
            >
              К выбору панели
            </button>
          </div>
        )}

        {showDoors && (
          <div className="gate-doors">
            <Door
              title="Панель сотрудника"
              detail={staffDetail}
              open={staffCanEnter}
              busy={phase === 'loading' || pendingAction === 'staff'}
              disabled={doorsDisabled}
              onClick={pressStaff}
            />
            <Door
              title="Панель администратора"
              detail={groupDetail}
              open={groupCanEnter}
              busy={phase === 'loading' || pendingAction === 'group'}
              disabled={doorsDisabled}
              onClick={pressGroup}
            />
          </div>
        )}
      </div>
    </div>
  )
}