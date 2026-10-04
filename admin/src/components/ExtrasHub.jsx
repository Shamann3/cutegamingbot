import { useMemo, useState } from 'react'
import { groupSections, SECTION_HINTS } from '../constants/panelNav'
import { NAV_ICONS } from './NavIcons'
import AccentPalette from './AccentPalette'
import SessionTimer from './SessionTimer'

function FallbackIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" aria-hidden="true">
      <rect x="5" y="5" width="14" height="14" rx="3" />
    </svg>
  )
}

/** На телефоне настройки сайдбара живут внизу «Ещё», под разделами. */
export function PanelPocketTools({
  accent,
  onAccentChange,
  lightMode = false,
  onTogglePerf,
  musicVolume = 0,
  onMusicVolumeChange,
  onToggleMusic,
  onChangeDoor,
  onExitPreview,
  onLogout,
  onSessionExpired,
  onReplayCoach,
}) {
  const muted = Number(musicVolume) <= 0
  return (
    <section className="pocket-tools" aria-label="Настройки панели">
      <h2 className="extras-hub-group-label">Настройки</h2>
      <div className="pocket-tools-card">
        {typeof onAccentChange === 'function' && (
          <AccentPalette value={accent} onChange={onAccentChange} />
        )}
        <SessionTimer compact onExpired={onSessionExpired} />
        {typeof onTogglePerf === 'function' && (
          <button type="button" className={`pocket-tools-row${lightMode ? ' is-on' : ''}`} onClick={onTogglePerf}>
            <strong>{lightMode ? 'Обычный режим' : 'Оптимизировать'}</strong>
            <span>{lightMode ? 'Вернуть матрицу и свечение' : 'Реже матрица, легче анимации'}</span>
          </button>
        )}
        {typeof onMusicVolumeChange === 'function' && (
          <label className="pocket-tools-music">
            <span>
              <strong>Музыка</strong>
              <button type="button" onClick={onToggleMusic}>{muted ? 'Включить' : 'Выключить'}</button>
            </span>
            <input
              type="range"
              min="0"
              max="100"
              value={Math.round(Number(musicVolume) * 100)}
              onChange={(event) => onMusicVolumeChange(Number(event.target.value) / 100)}
              aria-label="Громкость музыки"
            />
          </label>
        )}
        {typeof onReplayCoach === 'function' && (
          <button type="button" className="pocket-tools-row" onClick={onReplayCoach}>
            <strong>Показать обучение</strong>
            <span>Снова пройти короткие подсказки по панели</span>
          </button>
        )}
        {typeof onExitPreview === 'function' && (
          <button type="button" className="pocket-tools-row is-leave" onClick={onExitPreview}>
            <strong>Выйти из копии</strong>
            <span>Вернуться в «Стафф»</span>
          </button>
        )}
        {typeof onChangeDoor === 'function' && (
          <button type="button" className="pocket-tools-row" data-coach="doors" onClick={onChangeDoor}>
            <strong>Сменить панель</strong>
            <span>Выбор входа, без выхода из аккаунта</span>
          </button>
        )}
        {typeof onLogout === 'function' && (
          <button type="button" className="pocket-tools-row is-leave" onClick={onLogout}>
            <strong>Выйти</strong>
            <span>Завершить сессию</span>
          </button>
        )}
      </div>
    </section>
  )
}

/** Экран «Дополнительно»: сетка иконок остальных разделов. */
export default function ExtrasHub({
  sections = [],
  badges = {},
  onOpen,
  tools = null,
  footer = null,
}) {
  const [query, setQuery] = useState('')

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase().replace(/ё/g, 'е')
    const list = q
      ? sections.filter((item) => {
        const ru = (item.labelRu || '').toLowerCase().replace(/ё/g, 'е')
        const en = (item.label || '').toLowerCase()
        const id = (item.id || '').toLowerCase()
        const hint = (SECTION_HINTS[item.id] || '').toLowerCase().replace(/ё/g, 'е')
        return ru.includes(q) || en.includes(q) || id.includes(q) || hint.includes(q)
      })
      : sections
    return groupSections(list)
  }, [sections, query])

  return (
    <section className="extras-hub" aria-label="Дополнительно">
      <header className="extras-hub-head">
        <h1>Дополнительно</h1>
        <p>Все остальные разделы панели. Нажмите значок, чтобы открыть.</p>
      </header>

      <label className="extras-hub-search">
        <span className="extras-hub-search-icon" aria-hidden="true">⌕</span>
        <input
          className="extras-hub-search-field"
          type="text"
          inputMode="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Найти раздел…"
          aria-label="Найти раздел в дополнительно"
          enterKeyHint="search"
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
        />
      </label>

      {groups.length === 0 && (
        <p className="extras-hub-empty" role="status">Ничего не найдено</p>
      )}

      {groups.map((group) => (
        <div key={group.id} className="extras-hub-group">
          {group.label && (
            <h2 className="extras-hub-group-label">{group.label}</h2>
          )}
          <div className="extras-hub-grid">
            {group.items.map((item) => {
              const Icon = NAV_ICONS[item.id] || FallbackIcon
              const count = Number(badges[item.id] || 0)
              return (
                <button
                  key={item.id}
                  type="button"
                  className="extras-hub-tile"
                  onClick={() => onOpen?.(item.id)}
                >
                  <span className="extras-hub-icon">
                    <Icon />
                    {count > 0 && (
                      <i className="extras-hub-badge">{count > 99 ? '99+' : count}</i>
                    )}
                  </span>
                  <span className="extras-hub-name">{item.labelRu}</span>
                </button>
              )
            })}
          </div>
        </div>
      ))}
      {tools}
      {footer}
    </section>
  )
}
