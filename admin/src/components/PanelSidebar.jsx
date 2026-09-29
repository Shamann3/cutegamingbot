import { useEffect, useRef, useState } from 'react'
import { getAdminInitials, getAdminProfile } from '../lib/adminProfile'
import SessionTimer from './SessionTimer'
import EpsilonLogo from './EpsilonLogo'
import AccentPalette from './AccentPalette'
import { useIsPhone } from '../lib/useIsDesktop'
import { CopyableUsername } from './Copyable'
import { telegramDissolve } from '../lib/telegramDissolve'

const DISSOLVE_MS = 700

function SpeakerIcon({ muted }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      width="1em"
      height="1em"
      aria-hidden="true"
    >
      <path d="M4 9v6h4l5 4V5L8 9H4z" />
      {muted ? (
        <>
          <line x1="16" y1="9" x2="21" y2="14" />
          <line x1="21" y1="9" x2="16" y2="14" />
        </>
      ) : (
        <>
          <path d="M16.5 8.5a5 5 0 0 1 0 7" />
          <path d="M19 6a8.5 8.5 0 0 1 0 12" />
        </>
      )}
    </svg>
  )
}

function SettingsControls({
  accent,
  onAccentChange,
  onSessionExpired,
  musicVolume,
  onToggleMusic,
  onMusicVolumeChange,
  lightMode,
  onTogglePerf,
}) {
  return (
    <>
      <SessionTimer compact onExpired={onSessionExpired} />

      <div className="panel-music-card">
        <div className="panel-music-head">
          <button
            type="button"
            className="panel-music-icon-btn"
            onClick={onToggleMusic}
            title={musicVolume > 0 ? 'Выключить музыку' : 'Включить музыку'}
            aria-pressed={musicVolume > 0}
          >
            <SpeakerIcon muted={musicVolume <= 0} />
          </button>
          <span className="panel-music-label">Музыка</span>
          <span className="panel-music-pct">{Math.round(musicVolume * 100)}%</span>
        </div>
        <input
          type="range"
          className="panel-music-slider"
          min={0}
          max={100}
          step={1}
          value={Math.round(musicVolume * 100)}
          onChange={(e) => onMusicVolumeChange(Number(e.target.value) / 100)}
          style={{ '--vol-pct': `${Math.round(musicVolume * 100)}%` }}
          aria-label="Громкость музыки"
        />
      </div>

      <button
        type="button"
        className={`panel-perf-btn${lightMode ? ' panel-perf-btn-active' : ''}`}
        onClick={onTogglePerf}
        title={lightMode ? 'Максимальный интерфейс' : 'Оптимизировать интерфейс'}
      >
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          {lightMode ? (
            <path d="M12 3l2.2 5.2L20 10l-5.8 1.8L12 17l-2.2-5.2L4 10l5.8-1.8L12 3z" />
          ) : (
            <path d="M8 4h8l4 8-4 8H8l-4-8 4-8z" />
          )}
        </svg>
        {lightMode ? 'Максимальный интерфейс' : 'Оптимизировать интерфейс'}
      </button>
    </>
  )
}

export default function PanelSidebar({
  onLogout,
  onChangeDoor,
  onSessionExpired,
  mobileOpen = false,
  onClose,
  role = null,
  lightMode = false,
  onTogglePerf,
  musicVolume = 0,
  onMusicVolumeChange,
  onToggleMusic,
  accent = null,
  onAccentChange,
  brandName = 'Панель сотрудника',
  brandTag = 'Весь проект',
}) {
  const isPhone = useIsPhone()
  const { displayName, username, photoUrl } = getAdminProfile()
  const initials = getAdminInitials(displayName)
  const asideRef = useRef(null)
  const [visuallyOpen, setVisuallyOpen] = useState(mobileOpen)
  const [dissolving, setDissolving] = useState(false)
  const dissolvingRef = useRef(false)

  // Закрытие: испарение на частицы (как удаление сообщения в Telegram), ≤0.7с
  useEffect(() => {
    const el = asideRef.current
    if (mobileOpen) {
      dissolvingRef.current = false
      setDissolving(false)
      setVisuallyOpen(true)
      if (el) {
        el.style.visibility = ''
        el.style.pointerEvents = ''
        el.style.opacity = ''
      }
      return undefined
    }
    if (!visuallyOpen) return undefined
    if (dissolvingRef.current) return undefined
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
    if (reduce) {
      setVisuallyOpen(false)
      return undefined
    }
    dissolvingRef.current = true
    setDissolving(true)
    let cancelled = false
    ;(async () => {
      await telegramDissolve(el, { duration: DISSOLVE_MS })
      if (cancelled) return
      setVisuallyOpen(false)
      setDissolving(false)
      dissolvingRef.current = false
    })()
    return () => {
      cancelled = true
    }
  }, [mobileOpen, visuallyOpen])

  // Клик мимо панели закрывает её. Клик по панели палитру закрывает сама палитра.
  // Кнопку «Настройки» не трогаем: она сама переключает панель.
  // Вкладки дока закрывают панель и сразу открывают раздел.
  // Остальной клик гасится, чтобы не нажать кнопку под затемнением.
  useEffect(() => {
    if (!mobileOpen || typeof onClose !== 'function') return undefined
    let swallowTimer = 0
    const eatClick = (event) => {
      event.preventDefault()
      event.stopPropagation()
      document.removeEventListener('click', eatClick, true)
      window.clearTimeout(swallowTimer)
    }
    const armSwallow = () => {
      document.removeEventListener('click', eatClick, true)
      document.addEventListener('click', eatClick, true)
      window.clearTimeout(swallowTimer)
      swallowTimer = window.setTimeout(() => {
        document.removeEventListener('click', eatClick, true)
      }, 400)
    }
    const onPointer = (event) => {
      if (dissolvingRef.current) return
      const target = event.target
      const root = target?.closest?.('.panel-shelf-sidebar, .panel-dissolve-canvas')
      const toggle = target?.closest?.('.phone-dock-menu')
      const palette = target?.closest?.('.accent-picker-panel, .accent-picker-root, .accent-wheel-wrap, .accent-picker-backdrop')
      if (root || toggle || palette) return
      const dock = target?.closest?.('.phone-dock')
      onClose()
      if (!dock) armSwallow()
    }
    document.addEventListener('pointerdown', onPointer, true)
    return () => {
      document.removeEventListener('pointerdown', onPointer, true)
      document.removeEventListener('click', eatClick, true)
      window.clearTimeout(swallowTimer)
    }
  }, [mobileOpen, onClose])

  const settingsProps = {
    accent,
    onAccentChange,
    onSessionExpired,
    musicVolume,
    onToggleMusic,
    onMusicVolumeChange,
    lightMode,
    onTogglePerf,
  }

  return (
    <aside
      ref={asideRef}
      className={`panel-shelf panel-shelf-sidebar${mobileOpen || visuallyOpen ? ' panel-sidebar-mobile-open' : ''}${dissolving ? ' is-dissolving' : ''}`}
    >
      {(isPhone || mobileOpen) && (
        <div className="panel-sidebar-sheet-head">
          <p>Настройки</p>
          <button type="button" className="panel-sidebar-close" aria-label="Закрыть настройки" onClick={onClose}>
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>
      )}

      <div className="panel-brand" aria-label="Epsilon">
        <div className="panel-brand-crest" aria-hidden="true">
          <span className="panel-brand-halo" />
          <span className="panel-brand-ring" />
          <div className="panel-brand-mark">
            <EpsilonLogo size="sm" decorative />
          </div>
        </div>
        <div className="panel-brand-meta">
          <p className="panel-brand-name">{brandName}</p>
          <p className="panel-brand-tag">{brandTag}</p>
        </div>
      </div>

      <div className="panel-sidebar-footer">
        <div className="panel-sidebar-account">
          <div className="panel-profile-avatar" aria-hidden="true">
            {photoUrl ? (
              <img className="panel-profile-photo" src={photoUrl} alt="" />
            ) : (
              <span className="panel-profile-initials">{initials}</span>
            )}
          </div>
          <div className="panel-profile-meta">
            <p className="panel-profile-name">{displayName}</p>
            <p className="panel-profile-kicker">
              {role === 'owner' ? 'Владелец' : username ? <CopyableUsername value={username} /> : 'Cute Epsilon'}
            </p>
          </div>
        </div>

        <div className="panel-sidebar-settings panel-sidebar-settings-desktop">
          <div className="panel-sidebar-settings-body">
            <AccentPalette value={accent} onChange={onAccentChange} />
            <SettingsControls {...settingsProps} />
          </div>
        </div>

        {onChangeDoor && (
          <button type="button" className="panel-logout-btn" data-coach="doors" onClick={onChangeDoor}>
            Сменить панель
            <span className="panel-logout-hint">без выхода из аккаунта</span>
          </button>
        )}
        {onLogout && (
          <button type="button" className="panel-logout-btn" onClick={onLogout}>
            Выйти
          </button>
        )}
      </div>
    </aside>
  )
}
