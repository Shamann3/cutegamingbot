// Единый набор line-иконок для сайдбара — вместо эмодзи, которые по-разному
// рендерятся в разных Telegram WebView/ОС. Один язык: stroke=currentColor,
// круглые концы, viewBox 24×24 — цвет/анимация управляются через .panel-nav-icon.

const base = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.7,
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

const Dashboard = () => (
  <Icon>
    <rect x="3.5" y="3.5" width="7" height="7" rx="1.4" />
    <rect x="13.5" y="3.5" width="7" height="7" rx="1.4" />
    <rect x="3.5" y="13.5" width="7" height="7" rx="1.4" />
    <rect x="13.5" y="13.5" width="7" height="7" rx="1.4" />
  </Icon>
)

const Players = () => (
  <Icon>
    <circle cx="9" cy="8" r="3.2" />
    <path d="M3 20c0-3.9 2.7-6.4 6-6.4s6 2.5 6 6.4" />
    <circle cx="17" cy="8.5" r="2.4" />
    <path d="M15.3 13.4c2.9.3 4.9 2.6 4.9 6.1" />
  </Icon>
)

const Accounts = () => (
  <Icon>
    <circle cx="12" cy="8" r="3.6" />
    <path d="M4.5 20c0-4.3 3.4-7.2 7.5-7.2s7.5 2.9 7.5 7.2" />
  </Icon>
)

const Economy = () => (
  <Icon>
    <ellipse cx="12" cy="7" rx="7" ry="2.6" />
    <path d="M5 7v10c0 1.4 3.1 2.6 7 2.6s7-1.2 7-2.6V7" />
    <path d="M5 12c0 1.4 3.1 2.6 7 2.6s7-1.2 7-2.6" />
  </Icon>
)

const Market = () => (
  <Icon>
    <line x1="12" y1="3" x2="12" y2="19" />
    <line x1="4" y1="7" x2="20" y2="7" />
    <path d="M4 7l-2.2 5.2a3 3 0 0 0 4.4 0L4 7z" />
    <path d="M20 7l-2.2 5.2a3 3 0 0 0 4.4 0L20 7z" />
    <path d="M8.5 21h7" />
  </Icon>
)

const Farm = () => (
  <Icon>
    <path d="M12 21v-8" />
    <path d="M12 13c0-4-3-6-7-6 0 4 3 6 7 6z" />
    <path d="M12 11c0-3.4 2.6-5.2 6-5.2 0 3.4-2.6 5.2-6 5.2z" />
  </Icon>
)

const Content = () => (
  <Icon>
    <rect x="5" y="3" width="14" height="18" rx="1.6" />
    <line x1="8" y1="8" x2="16" y2="8" />
    <line x1="8" y1="12" x2="16" y2="12" />
    <line x1="8" y1="16" x2="13" y2="16" />
  </Icon>
)

const Giveaways = () => (
  <Icon>
    <rect x="4" y="10" width="16" height="9.5" rx="1.4" />
    <path d="M4 13.5h16" />
    <path d="M12 10v9.5" />
    <path d="M12 10c-1.8 0-4-1-4-3.1C8 5.3 9.2 4 10.6 4c1.7 0 2.9 2.3 3.4 4.3" />
    <path d="M12 10c1.8 0 4-1 4-3.1 0-1.6-1.2-2.9-2.6-2.9-1.7 0-2.9 2.3-3.4 4.3" />
  </Icon>
)

const Broadcast = () => (
  <Icon>
    <circle cx="12" cy="18" r="1.4" />
    <path d="M8.5 14.5a5 5 0 0 1 7 0" />
    <path d="M5.5 11.5a9 9 0 0 1 13 0" />
  </Icon>
)

const Logs = () => (
  <Icon>
    <circle cx="5.5" cy="6" r="1" fill="currentColor" stroke="none" />
    <circle cx="5.5" cy="12" r="1" fill="currentColor" stroke="none" />
    <circle cx="5.5" cy="18" r="1" fill="currentColor" stroke="none" />
    <line x1="9.5" y1="6" x2="19" y2="6" />
    <line x1="9.5" y1="12" x2="19" y2="12" />
    <line x1="9.5" y1="18" x2="19" y2="18" />
  </Icon>
)

const Analytics = () => (
  <Icon>
    <line x1="3" y1="20" x2="21" y2="20" />
    <line x1="6" y1="20" x2="6" y2="13" strokeWidth="2.6" />
    <line x1="12" y1="20" x2="12" y2="7" strokeWidth="2.6" />
    <line x1="18" y1="20" x2="18" y2="16" strokeWidth="2.6" />
  </Icon>
)

const Events = () => (
  <Icon>
    <rect x="4" y="5" width="16" height="15" rx="1.6" />
    <line x1="4" y1="9.5" x2="20" y2="9.5" />
    <line x1="8" y1="3" x2="8" y2="6.5" />
    <line x1="16" y1="3" x2="16" y2="6.5" />
    <circle cx="12" cy="14.5" r="1.2" fill="currentColor" stroke="none" />
  </Icon>
)

const Settings = () => (
  <Icon>
    <line x1="4" y1="6" x2="20" y2="6" />
    <circle cx="9" cy="6" r="1.7" />
    <line x1="4" y1="12" x2="20" y2="12" />
    <circle cx="15" cy="12" r="1.7" />
    <line x1="4" y1="18" x2="20" y2="18" />
    <circle cx="11" cy="18" r="1.7" />
  </Icon>
)

const Staff = () => (
  <Icon>
    <rect x="5" y="4" width="14" height="17" rx="2" />
    <circle cx="12" cy="10" r="2.6" />
    <path d="M8 16.4c0-1.8 1.8-2.8 4-2.8s4 1 4 2.8" />
  </Icon>
)

const Support = () => (
  <Icon>
    <path d="M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v7a2.5 2.5 0 0 1-2.5 2.5H10l-4.5 4v-4H6.5A2.5 2.5 0 0 1 4 13.5v-7z" />
  </Icon>
)

const Security = () => (
  <Icon>
    <path d="M12 3l7 3v5c0 5-3.2 8.4-7 10-3.8-1.6-7-5-7-10V6l7-3z" />
    <path d="M9 12l2.2 2.2L15.5 10" />
  </Icon>
)

const Moderation = () => (
  <Icon>
    <rect x="4" y="4" width="16" height="4.5" rx="1" />
    <path d="M5 8.5v9.5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8.5" />
    <line x1="10" y1="12.5" x2="14" y2="12.5" />
  </Icon>
)

const Chronicle = () => (
  <Icon>
    <path d="M12 6.5c-1.8-1.4-4.3-2-6.8-2-.7 0-1.2.5-1.2 1.2v11.6c0 .7.5 1.2 1.2 1.2 2.5 0 5 .6 6.8 2 1.8-1.4 4.3-2 6.8-2 .7 0 1.2-.5 1.2-1.2V5.7c0-.7-.5-1.2-1.2-1.2-2.5 0-5 .6-6.8 2z" />
    <line x1="12" y1="6.5" x2="12" y2="18.3" />
  </Icon>
)

export const NAV_ICONS = {
  dashboard: Dashboard,
  users: Players,
  accounts: Accounts,
  economy: Economy,
  market: Market,
  farm: Farm,
  content: Content,
  giveaways: Giveaways,
  broadcast: Broadcast,
  logs: Logs,
  analytics: Analytics,
  events: Events,
  settings: Settings,
  staff: Staff,
  support: Support,
  security: Security,
  moderation: Moderation,
  chronicle: Chronicle,
}
