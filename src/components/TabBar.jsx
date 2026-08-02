import { useOnboardingOptional } from '../context/OnboardingContext'
import { useQuestBadge } from '../hooks/useQuests'
import { TAB_ACCENTS, TAB_ICONS } from './TabIcons'

const PRIMARY = [
  { id: 'farm', label: 'Ферма' },
  { id: 'trade', label: 'Торговля' },
  { id: 'quests', label: 'Задания' },
  { id: 'profile', label: 'Профиль' },
]

export default function TabBar({ active, onChange }) {
  const onboarding = useOnboardingOptional()
  const pulseTab = onboarding?.pulseTab ?? null
  const questBadge = useQuestBadge()

  return (
    <nav className="app-tab-bar" aria-label="Разделы приложения">
      <div className="app-tab-bar-inner">
        {PRIMARY.map((tab) => {
          const isActive = active === tab.id
          const isPulsing = pulseTab === tab.id
          const TabIcon = TAB_ICONS[tab.id]
          const accent = TAB_ACCENTS[tab.id]
          const showBadge = tab.id === 'quests' && questBadge > 0 && !isActive
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
                {showBadge ? (
                  <span className="app-tab-badge" aria-label={`${questBadge} наград`}>
                    {questBadge > 9 ? '9+' : questBadge}
                  </span>
                ) : null}
              </span>
              <span className="app-tab-label">{tab.label}</span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}
