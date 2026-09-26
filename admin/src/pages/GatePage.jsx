import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchAdminAuthStatus } from '../lib/adminClient'
import { accentIsPersonal, loadStoredAccent } from '../lib/accentTheme'
import { portraitFrom } from '../lib/gateRecovery'
import EpsilonLogo from '../components/EpsilonLogo'
import ColorChoice from '../components/ColorChoice'

function Door({ title, detail, open, onClick }) {
  return (
    <button
      type="button"
      className={`gate-door${open ? ' is-open' : ' is-sealed'}`}
      onClick={onClick}
    >
      <span className="gate-door-title">{title}</span>
      <span className="gate-door-detail">{detail}</span>
      <span className="gate-door-mark">{open ? 'Войти' : 'Закрыто'}</span>
    </button>
  )
}

export default function GatePage({ onStaffEnter, onStaffApply, onGroupEnter, onGroupApply }) {
  const [personal, setPersonal] = useState(() => accentIsPersonal(loadStoredAccent()))
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [portrait, setPortrait] = useState(null)
  const [hold, setHold] = useState(false)
  const requestId = useRef(0)

  const load = useCallback(() => {
    const id = requestId.current + 1
    requestId.current = id
    setLoading(true)
    setError('')
    fetchAdminAuthStatus()
      .then((status) => {
        if (requestId.current !== id) return
        setPortrait(portraitFrom(status))
      })
      .catch((err) => {
        if (requestId.current !== id) return
        setPortrait(null)
        setError(err.message || 'Не удалось сверить доступ')
      })
      .finally(() => {
        if (requestId.current === id) setLoading(false)
      })
  }, [])

  useEffect(() => load(), [load])

  const staffDetail = portrait?.staffCanEnter
    ? 'Команда проекта. Дальше ключ и код из аутентификатора.'
    : portrait?.applicationStatus === 'pending'
      ? 'Заявка уже у создателя. Повторно отправлять не нужно.'
      : 'Для команды проекта. Нажатие откроет заявку, не панель.'

  const groupDetail = portrait?.groupCanEnter
    ? (portrait.groups.length > 1 ? 'Ваши группы. Дальше спросит, какую открыть.' : 'Кабинет этой группы: люди, архив, наказания.')
    : 'Для администраторов групп. Нажатие откроет заявку, не панель.'

  const pressStaff = () => {
    if (!portrait) return
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
    if (!portrait) return
    if (portrait.groupCanEnter) onGroupEnter(portrait)
    else onGroupApply()
  }

  return (
    <div className={`gate-root${personal ? ' is-personal' : ''}`}>
      <div className="gate-frame" aria-hidden="true" />
      <div className="gate-sheet">
        <header className="gate-head">
          <EpsilonLogo size="sm" decorative />
          <h1 className="gate-title">Куда войти</h1>
          <p className="gate-lead">Два входа. Яркая кнопка открывает панель. Серая кнопка панель не открывает: она начинает заявку.</p>
          <ColorChoice onChange={(next) => setPersonal(accentIsPersonal(next))} />
        </header>

        {loading && (
          <div className="realm-load" role="status">
            <span />
            <p>Сверка допуска</p>
          </div>
        )}

        {!loading && error && (
          <div className="gate-recover" role="alert">
            <p className="gate-status gate-status-error">{error}</p>
            <p className="gate-lead">Проверка не прошла. Панель можно открыть вручную: если доступа нет, она вернёт к выбору.</p>
            <div className="gate-recover-actions">
              <button type="button" className="firstrun-next" onClick={load}>Повторить сверку</button>
              <button type="button" className="gate-text" onClick={onStaffEnter}>Панель сотрудника</button>
              <button type="button" className="gate-text" onClick={onStaffApply}>Заявка в команду</button>
              <button type="button" className="gate-text" onClick={onGroupApply}>Заявка в группу</button>
            </div>
          </div>
        )}

        {!loading && !error && hold && (
          <div className="gate-hold" role="status">
            <h2 className="gate-title">Заявка уже у создателя</h2>
            <p className="gate-lead">Вход откроется после одобрения. Повторно отправлять её не нужно.</p>
            <button type="button" className="gate-text" onClick={() => setHold(false)}>К выбору панели</button>
          </div>
        )}

        {!loading && !error && !hold && portrait && (
          <div className="gate-doors">
            <Door
              title="Панель сотрудника"
              detail={staffDetail}
              open={portrait.staffCanEnter}
              onClick={pressStaff}
            />
            <Door
              title="Панель администратора"
              detail={groupDetail}
              open={portrait.groupCanEnter}
              onClick={pressGroup}
            />
          </div>
        )}
      </div>
    </div>
  )
}
