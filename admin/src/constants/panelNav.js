/** Разделы admin-панели. id = ключ экрана. */

export const PANEL_SECTIONS = [
  { id: 'dashboard', label: 'Dashboard', labelRu: 'Главная' },
  { id: 'users',     label: 'Players',         labelRu: 'Игроки',       permission: 'view_players' },
  { id: 'accounts',  label: 'Accounts',        labelRu: 'Пользователи', permission: 'view_accounts' },
  { id: 'economy',   label: 'Economy',         labelRu: 'Экономика',    permission: 'manage_economy' },
  { id: 'market',    label: 'Market',          labelRu: 'Биржа',        permission: 'view_market' },
  { id: 'farm',      label: 'Farm Management', labelRu: 'Ферма',        permission: 'manage_farm' },
  { id: 'content',   label: 'Content',         labelRu: 'Контент',      permission: 'manage_content' },
  { id: 'broadcast', label: 'Broadcast',       labelRu: 'Рассылка',     permission: 'manage_broadcast' },
  { id: 'logs',      label: 'Logs',            labelRu: 'Логи',         permission: 'view_logs' },
  { id: 'analytics', label: 'Analytics',       labelRu: 'Аналитика',    permission: 'view_analytics' },
  { id: 'events',    label: 'Events',          labelRu: 'Ивенты',       permission: 'manage_events' },
  { id: 'settings',  label: 'Settings',        labelRu: 'Настройки',    permission: 'manage_settings' },
  { id: 'staff',     label: 'Staff',           labelRu: 'Стафф' },
  { id: 'support',   label: 'Support',         labelRu: 'Поддержка' },
  { id: 'security',  label: 'Security',        labelRu: 'Доступ',       permission: 'manage_security' },
  { id: 'moderation', label: 'Moderation',     labelRu: 'Архив' },
  { id: 'chronicle',  label: 'Chronicle',       labelRu: 'Хронология' },
]

/** Секции, видимые с учётом прав текущего админа. */
export function visibleSections(permissions = []) {
  const perms = new Set(permissions)
  return PANEL_SECTIONS.filter((s) => !s.permission || perms.has(s.permission))
}

export function getSectionById(id) {
  return PANEL_SECTIONS.find((s) => s.id === id) ?? PANEL_SECTIONS[0]
}
