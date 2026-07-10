import { useState } from 'react'
import { useOnboardingOptional } from '../context/OnboardingContext'
import { useQuestBadge } from '../hooks/useQuests'
import MoreMenu, { SECONDARY_TABS } from './MoreMenu'
import { TAB_ACCENTS, TAB_ICONS } from './TabIcons'

const PRIMARY = [
  { id: 'farm', label: 'Ферма' },
  { id: 'inventory', label: 'Инвентарь' },
  { id: 'shop', label: 'Магазин' },
]

const SECONDARY_IDS = new Set(SECONDARY_TABS.map((tab) => tab.id))

export default function TabBar({ active, onChange }) {
  const onboarding = useOnboardingOptional()
  const pulseTab = onboarding?.pulseTab ?? null
  const questBadge = useQuestBadge()
  const [moreOpen, setMoreOpen] = useState(false)

  const isSecondaryActive = SECONDARY_IDS.has(active)
  const showMoreBadge = questBadge > 0 && active !== 'quests'
  const MoreIcon = TAB_ICONS.more

  const handleMoreChange = (id) => {
    onChange(id)
    setMoreOpen(false)
  }

  return (
    <nav
      className="app-tab-bar"
      aria-label="Разделы приложения"
    >
      <div className="app-tab-bar-inner">
        {PRIMARY.map((tab) => {
          const isActive = active === tab.id
          const isPulsing = pulseTab === tab.id
          const TabIcon = TAB_ICONS[tab.id]
          const accent = TAB_ACCENTS[tab.id]
          return (
            <button
              key={tab.id}
              type="button"
              className={`app-tab-btn ${isActive ? 'app-tab-btn-active' : ''} ${isPulsing ? 'app-tab-btn-pulse' : ''}`}
              data-onboarding-tab={tab.id}
              data-tab={tab.id}
              aria-current={isActive ? 'page' : undefined}
              onClick={() => onChange(tab.id)}
              style={accent ? { '--tab-icon-strong': accent.strong, '--tab-icon-glow': accent.glow } : undefined}
            >
              <span className="app-tab-icon-wrap">
                <span className="app-tab-icon">{TabIcon && <TabIcon />}</span>
              </span>
              <span className="app-tab-label">{tab.label}</span>
            </button>
          )
        })}
        <button
          type="button"
          className={`app-tab-btn ${isSecondaryActive ? 'app-tab-btn-active' : ''}`}
          data-tab="more"
          aria-current={isSecondaryActive ? 'page' : undefined}
          aria-expanded={moreOpen}
          onClick={() => setMoreOpen((open) => !open)}
          style={{ '--tab-icon-strong': TAB_ACCENTS.more.strong, '--tab-icon-glow': TAB_ACCENTS.more.glow }}
        >
          <span className="app-tab-icon-wrap">
            <span className="app-tab-icon">{MoreIcon && <MoreIcon />}</span>
            {showMoreBadge ? (
              <span className="app-tab-badge" aria-label={`${questBadge} наград`}>
                {questBadge > 9 ? '9+' : questBadge}
              </span>
            ) : null}
          </span>
          <span className="app-tab-label">Ещё</span>
        </button>
      </div>

      <MoreMenu isOpen={moreOpen} onClose={() => setMoreOpen(false)} active={active} onChange={handleMoreChange} />
    </nav>
  )
}
