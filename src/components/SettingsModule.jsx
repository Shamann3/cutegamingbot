import { useEffect, useState } from 'react'
import FarmBackground from './FarmBackground'
import TabAtmosphere from './TabAtmosphere'
import VineFrame from './VineFrame'
import { musicVolumeLabel } from '../constants/musicVolume'
import { PERF_MODES } from '../constants/performance'
import { useSettings } from '../context/SettingsContext'
import { apiRequest, getSupportBotUrl } from '../lib/apiClient'

const PERF_OPTIONS = [
  {
    id: PERF_MODES.FULL,
    emoji: '✨',
    label: 'Все эффекты',
    desc: 'Полная картинка',
  },
  {
    id: PERF_MODES.LITE,
    emoji: '🪶',
    label: 'Лёгкий',
    desc: 'Меньше анимаций, быстрее на большинстве телефонов',
  },
  {
    id: PERF_MODES.TURBO,
    emoji: '⚡',
    label: 'Турбо',
    desc: 'Минимум нагрузки для слабых устройств',
  },
]

export default function SettingsModule() {
  const {
    soundEnabled,
    toggleSound,
    musicVolume,
    setMusicVolume,
    performanceMode,
    setPerformanceMode,
  } = useSettings()

  const [harvestNotify, setHarvestNotify] = useState(false)
  const [notifyLoading, setNotifyLoading] = useState(false)

  useEffect(() => {
    apiRequest('/api/settings')
      .then((d) => setHarvestNotify(Boolean(d.harvestNotify)))
      .catch(() => {})
  }, [])

  const toggleHarvestNotify = async () => {
    if (notifyLoading) return
    const next = !harvestNotify
    setHarvestNotify(next)
    setNotifyLoading(true)
    try {
      await apiRequest('/api/settings/harvest-notify', {
        method: 'POST',
        body: { enabled: next },
      })
    } catch {
      setHarvestNotify(!next)
    } finally {
      setNotifyLoading(false)
    }
  }

  const openSupport = () => {
    const url = getSupportBotUrl()
    if (!url) return
    try {
      if (window.Telegram?.WebApp?.openTelegramLink) {
        window.Telegram.WebApp.openTelegramLink(url)
      } else {
        window.open(url, '_blank', 'noopener')
      }
    } catch {
      window.open(url, '_blank', 'noopener')
    }
  }

  return (
    <div className="relative min-h-screen tab-theme-settings settings-module">
      <FarmBackground />
      <TabAtmosphere variant="settings" />

      <div className="relative z-10 settings-shell py-4 pb-2 animate-slide-up">
        <header className="settings-hero">
          <p className="settings-hero-eyebrow">Cute</p>
          <h1 className="settings-hero-title">Настройки</h1>
        </header>

        <VineFrame className="settings-panel-frame">
          <section className="settings-section" aria-labelledby="settings-sound-title">
            <h2 id="settings-sound-title" className="settings-section-title">
              Звук
            </h2>

            <div className="shop-sheet-settings">
              <div className="shop-sheet-toggle-row">
                <div className="shop-sheet-toggle-copy">
                  <span className="shop-sheet-toggle-icon" aria-hidden>
                    {soundEnabled ? '🔊' : '🔇'}
                  </span>
                  <div>
                    <span className="shop-sheet-toggle-label">
                      {soundEnabled ? 'Звук включён' : 'Звук выключен'}
                    </span>
                    <span className="shop-sheet-toggle-desc">
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  className={`shop-sheet-switch ${soundEnabled ? 'shop-sheet-switch-on' : ''}`}
                  role="switch"
                  aria-checked={soundEnabled}
                  aria-label={soundEnabled ? 'Выключить звук' : 'Включить звук'}
                  onClick={toggleSound}
                >
                  <span className="shop-sheet-switch-thumb" aria-hidden />
                </button>
              </div>

              <div className={`settings-music-volume ${soundEnabled ? '' : 'settings-music-volume--disabled'}`}>
                <div className="settings-music-volume-head">
                  <span className="settings-music-volume-icon" aria-hidden>🎵</span>
                  <div className="settings-music-volume-copy">
                    <span className="shop-sheet-toggle-label">Громкость музыки</span>
                    <span className="shop-sheet-toggle-desc">{musicVolumeLabel(musicVolume)}</span>
                  </div>
                  <span className="settings-music-volume-value" aria-hidden>{musicVolume}%</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={100}
                  step={5}
                  value={musicVolume}
                  disabled={!soundEnabled}
                  onChange={(event) => setMusicVolume(Number(event.target.value))}
                  className="settings-music-volume-slider"
                  aria-label="Громкость фоновой музыки"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={musicVolume}
                  aria-valuetext={musicVolumeLabel(musicVolume)}
                />
              </div>
            </div>
          </section>

          <section className="settings-section" aria-labelledby="settings-notify-title">
            <h2 id="settings-notify-title" className="settings-section-title">
              Уведомления
            </h2>
            <div className="shop-sheet-settings">
              <div className="shop-sheet-toggle-row">
                <div className="shop-sheet-toggle-copy">
                  <span className="shop-sheet-toggle-icon" aria-hidden>
                    {harvestNotify ? '🔔' : '🔕'}
                  </span>
                  <div>
                    <span className="shop-sheet-toggle-label">
                      Урожай
                    </span>
                    <span className="shop-sheet-toggle-desc">
                      Уведомления о созревании грядок
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  className={`shop-sheet-switch ${harvestNotify ? 'shop-sheet-switch-on' : ''}`}
                  role="switch"
                  aria-checked={harvestNotify}
                  aria-label={harvestNotify ? 'Выключить уведомления' : 'Включить уведомления'}
                  disabled={notifyLoading}
                  onClick={toggleHarvestNotify}
                >
                  <span className="shop-sheet-switch-thumb" aria-hidden />
                </button>
              </div>
            </div>
          </section>

          <section className="settings-section" aria-labelledby="settings-perf-title">
            <h2 id="settings-perf-title" className="settings-section-title">
              Оптимизация
            </h2>
            <p className="settings-section-hint">
              Выберите режим графики.
            </p>

            <div className="shop-sheet-options settings-perf-options" role="radiogroup" aria-label="Режим графики">
              {PERF_OPTIONS.map((option) => {
                const selected = performanceMode === option.id
                return (
                  <button
                    key={option.id}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    className={`shop-sheet-option settings-perf-option ${selected ? 'shop-sheet-option-selected' : ''}`}
                    onClick={() => setPerformanceMode(option.id)}
                  >
                    <span
                      className={`shop-sheet-radio-dot ${selected ? 'shop-sheet-radio-dot-selected' : ''}`}
                      aria-hidden
                    />
                    <span className="settings-perf-option-body">
                      <span className="settings-perf-option-head">
                        <span className="settings-perf-option-emoji" aria-hidden>{option.emoji}</span>
                        <span className="shop-sheet-option-label">{option.label}</span>
                      </span>
                      <span className="settings-perf-option-desc">{option.desc}</span>
                    </span>
                  </button>
                )
              })}
            </div>
          </section>

          <section className="settings-section" aria-labelledby="settings-support-title">
            <h2 id="settings-support-title" className="settings-section-title">
              Поддержка
            </h2>
            <p className="settings-section-hint">
              Вопросы, проблемы с аккаунтом, баги - напишите нам, ответим как можно скорее.
            </p>
            <button
              type="button"
              className="settings-complaint-btn"
              onClick={openSupport}
              disabled={!getSupportBotUrl()}
            >
              💬 Написать в поддержку
            </button>
          </section>
        </VineFrame>
      </div>
    </div>
  )
}
