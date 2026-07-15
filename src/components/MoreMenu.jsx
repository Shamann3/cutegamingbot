import { useQuestBadge } from '../hooks/useQuests'
import BottomSheet from './BottomSheet'
import { TAB_ACCENTS, TAB_ICONS } from './TabIcons'

export const SECONDARY_TABS = [
  { id: 'craft', label: 'Крафты' },
  { id: 'quests', label: 'Задания' },
  { id: 'market', label: 'Биржа' },
  { id: 'profile', label: 'Профиль' },
  { id: 'settings', label: 'Настройки' },
]

export default function MoreMenu({ isOpen, onClose, active, onChange }) {
  const questBadge = useQuestBadge()

  return (
    <BottomSheet isOpen={isOpen} onClose={onClose} title="Ещё" showApply={false}>
      <div
        className="more-menu-list"
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '12px',
          padding: '16px'
        }}
      >
        {SECONDARY_TABS.map((tab) => {
          const isActive = active === tab.id
          const showBadge = tab.id === 'quests' && questBadge > 0 && !isActive
          const TabIcon = TAB_ICONS[tab.id]
          const accent = TAB_ACCENTS[tab.id]

          return (
            <button
              key={tab.id}
              type="button"
              className={`more-menu-item ${isActive ? 'more-menu-item-active' : ''}`}
              onClick={() => onChange(tab.id)}
              onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = `0 8px 24px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.15)` }}
              onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = `0 4px 12px rgba(0,0,0,0.3), 0 0 0 1px rgba(255,255,255,0.05)` }}
              onMouseDown={(e) => { e.currentTarget.style.transform = 'scale(.97)' }}
              onMouseUp={(e) => { e.currentTarget.style.transform = 'translateY(-2px)' }}
              style={accent ? {
                // ЭФФЕКТ СТЕКЛА: полупрозрачный градиент в цвет вкладки поверх тёмной карточки.
                // accent содержит только { strong, glow } (см. TAB_ACCENTS), поэтому строим фон
                // из accent.glow это уже translucent rgba, даёт стеклянный оттенок вкладки.
                background: `linear-gradient(180deg, ${accent.glow} 0%, rgba(6, 16, 10, 0.85) 100%)`,
                backdropFilter: 'blur(8px)', // Размытие фона под кнопкой
                WebkitBackdropFilter: 'blur(8px)',

                border: '1px solid rgba(255, 255, 255, 0.08)', // Тонкая светлая грань
                borderRadius: '18px',
                padding: '14px 16px',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                width: '100%',
                cursor: 'pointer',
                transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                position: 'relative',
                // Глубокая тень
                boxShadow: `0 4px 12px rgba(0,0,0,0.3), 0 0 0 1px rgba(255,255,255,0.05)`,
              } : undefined}
            >
              <span className="more-menu-icon" style={{
                color: '#fff', // Делаем иконки белыми, чтобы они «светились» сквозь стекло
                opacity: 0.9,
                display: 'flex',
                filter: `drop-shadow(0 0 6px ${accent.strong})` // Легкое свечение иконки
              }}>
                {TabIcon && <TabIcon />}
              </span>

              <span style={{
                color: '#ffffff',
                fontWeight: '600',
                fontSize: '15px',
                textShadow: '0 1px 2px rgba(0,0,0,0.3)' // Тень для текста, чтобы он читался лучше
              }}>
                {tab.label}
              </span>
            </button>
          )
        })}
      </div>
    </BottomSheet>
  )
}