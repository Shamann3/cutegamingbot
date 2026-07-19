// Единый набор line-иконок для нижнего таб-бара вместо эмодзи, которые
// неровно рендерятся между iOS/Android/десктоп Telegram. stroke=currentColor,
// поэтому цвет (тусклый/акцент вкладки) управляется через CSS в TabBar.

const base = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
}

function Icon({ children }) {
  return (
    <svg {...base} aria-hidden="true">
      {children}
    </svg>
  )
}

const Farm = () => (
  <Icon>
    <line x1="4" y1="20" x2="20" y2="20" />
    <path d="M12 20v-6.5" />
    <path d="M12 13.5c0-3.3-2.5-5-5.8-5 0 3.3 2.5 5 5.8 5z" />
    <path d="M12 11.7c0-2.8 2.1-4.2 5-4.2 0 2.8-2.1 4.2-5 4.2z" />
  </Icon>
)

const Inventory = () => (
  <Icon>
    <path d="M8 8V6a4 4 0 0 1 8 0v2" />
    <rect x="5" y="8" width="14" height="13" rx="2.5" />
    <path d="M9 8v3.2c0 .7.6 1.3 1.3 1.3h3.4c.7 0 1.3-.6 1.3-1.3V8" />
  </Icon>
)

const Craft = () => (
  <Icon>
    <path d="M10 3h4" />
    <path d="M11 3v5.2L6.3 17a2 2 0 0 0 1.8 2.9h7.8a2 2 0 0 0 1.8-2.9L13 8.2V3" />
    <line x1="8.5" y1="14" x2="15.5" y2="14" />
  </Icon>
)

const Quests = () => (
  <Icon>
    <rect x="5" y="3" width="14" height="18" rx="2" />
    <path d="M8.5 9.3l1.4 1.4L12.7 8" />
    <line x1="9" y1="14.2" x2="15" y2="14.2" />
    <line x1="9" y1="17.2" x2="13" y2="17.2" />
  </Icon>
)

const Shop = () => (
  <Icon>
    <path d="M4 8l1.2-4h13.6L20 8" />
    <path d="M4 8h16v11a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 19V8z" />
    <path d="M9 8v2.2a3 3 0 0 0 6 0V8" />
  </Icon>
)

const Market = () => (
  <Icon>
    <path d="M4 8h13" />
    <path d="M14 4l3 4-3 4" />
    <path d="M20 16H7" />
    <path d="M10 20l-3-4 3-4" />
  </Icon>
)

const Chests = () => (
  <Icon>
    <rect x="4" y="10" width="16" height="9" rx="1.5" />
    <path d="M4 10l1-4.5A2 2 0 0 1 6.9 4h10.2a2 2 0 0 1 1.9 1.5L20 10" />
    <line x1="4" y1="14" x2="20" y2="14" />
    <path d="M10.5 14v1.6a1.5 1.5 0 0 0 3 0V14" />
  </Icon>
)

const Profile = () => (
  <Icon>
    <circle cx="12" cy="8.2" r="3.6" />
    <path d="M4.8 20c0-4.3 3.3-7 7.2-7s7.2 2.7 7.2 7" />
  </Icon>
)

const Settings = () => (
  <Icon>
    <circle cx="12" cy="12" r="3.4" />
    <line x1="12" y1="3.5" x2="12" y2="6" />
    <line x1="12" y1="18" x2="12" y2="20.5" />
    <line x1="3.5" y1="12" x2="6" y2="12" />
    <line x1="18" y1="12" x2="20.5" y2="12" />
    <line x1="6.2" y1="6.2" x2="7.9" y2="7.9" />
    <line x1="16.1" y1="16.1" x2="17.8" y2="17.8" />
    <line x1="6.2" y1="17.8" x2="7.9" y2="16.1" />
    <line x1="16.1" y1="7.9" x2="17.8" y2="6.2" />
  </Icon>
)

const More = () => (
  <Icon>
    <circle cx="5" cy="12" r="1.6" fill="currentColor" stroke="none" />
    <circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none" />
    <circle cx="19" cy="12" r="1.6" fill="currentColor" stroke="none" />
  </Icon>
)

const Gift = () => (
  <Icon>
    <rect x="4" y="9" width="16" height="11" rx="1.5" />
    <path d="M4 9h16" />
    <path d="M12 9v11" />
    <path d="M12 9c-1.6-3.6-6-3.6-6-1 0 1 .9 1 2 1" />
    <path d="M12 9c1.6-3.6 6-3.6 6-1 0 1-.9 1-2 1" />
  </Icon>
)

export const TAB_ICONS = {
  farm: Farm,
  inventory: Inventory,
  craft: Craft,
  quests: Quests,
  shop: Shop,
  market: Market,
  chests: Chests,
  profile: Profile,
  settings: Settings,
  more: More,
  trade: Market,
  giveaways: Gift,
}

// Те же значения, что в src/styles/tabThemes.css (--tab-accent-strong / --tab-accent-glow)
// держать в синхроне, если поменяются там.
export const TAB_ACCENTS = {
  farm: { strong: '#34d399', glow: 'rgba(52, 211, 153, 0.32)' },
  inventory: { strong: '#d97706', glow: 'rgba(217, 119, 6, 0.3)' },
  craft: { strong: '#a78bfa', glow: 'rgba(124, 58, 237, 0.34)' },
  quests: { strong: '#f97316', glow: 'rgba(249, 115, 22, 0.32)' },
  shop: { strong: '#f59e0b', glow: 'rgba(251, 191, 36, 0.3)' },
  market: { strong: '#b87333', glow: 'rgba(184, 115, 51, 0.32)' },
  chests: { strong: '#e6b422', glow: 'rgba(230,180,34,0.5)' },
  profile: { strong: '#22d3ee', glow: 'rgba(34, 211, 238, 0.32)' },
  settings: { strong: '#64748b', glow: 'rgba(100, 116, 139, 0.32)' },
  more: { strong: '#d4af37', glow: 'rgba(212, 175, 55, 0.32)' },
  trade: { strong: '#cd9b5a', glow: 'rgba(184, 115, 51, 0.32)' },
  giveaways: { strong: '#f472b6', glow: 'rgba(244, 114, 182, 0.34)' },
}
