/** Разделы admin-панели. id = ключ экрана, group = блок в сайдбаре. */

export const PANEL_SECTIONS = [
  { id: 'dashboard', label: 'Dashboard',       labelRu: 'Главная',      group: 'overview' },
  { id: 'users',     label: 'Players',         labelRu: 'Игроки',       group: 'people',  permission: 'view_players' },
  { id: 'accounts',  label: 'Accounts',        labelRu: 'Пользователи', group: 'people',  permission: 'view_accounts' },
  { id: 'moderation', label: 'Moderation',     labelRu: 'Архив',        group: 'people' },
  { id: 'economy',   label: 'Economy',         labelRu: 'Экономика',    group: 'economy', permission: 'manage_economy' },
  { id: 'market',    label: 'Market',          labelRu: 'Биржа',        group: 'economy', permission: 'view_market' },
  { id: 'farm',      label: 'Farm Management', labelRu: 'Ферма',        group: 'economy', permission: 'manage_farm' },
  { id: 'content',   label: 'Content',         labelRu: 'Контент',      group: 'content', permission: 'manage_content' },
  { id: 'giveaways', label: 'Giveaways',       labelRu: 'Розыгрыши',    group: 'content', permission: 'manage_content' },
  { id: 'events',    label: 'Events',          labelRu: 'Ивенты',       group: 'content', permission: 'manage_events' },
  { id: 'broadcast', label: 'Broadcast',       labelRu: 'Рассылка',     group: 'content', permission: 'manage_broadcast' },
  { id: 'staff',     label: 'Staff',           labelRu: 'Стафф',        group: 'team' },
  { id: 'support',   label: 'Support',         labelRu: 'Поддержка',    group: 'team' },
  { id: 'analytics', label: 'Analytics',       labelRu: 'Аналитика',    group: 'insights', permission: 'view_analytics' },
  { id: 'logs',      label: 'Logs',            labelRu: 'Логи',         group: 'insights', permission: 'view_logs' },
  { id: 'chronicle', label: 'Chronicle',       labelRu: 'Хронология',   group: 'insights' },
  { id: 'settings',  label: 'Settings',        labelRu: 'Настройки',    group: 'system',  permission: 'manage_settings' },
  { id: 'security',  label: 'Security',        labelRu: 'Доступ',       group: 'system',  permission: 'manage_security' },
  { id: 'panelAccess', label: 'Admin Panel',   labelRu: 'Админ панель', group: 'system',  permission: 'manage_panel_access' },
]

/** Блоки сайдбара. Порядок здесь = порядок в меню.
 *  label: null — блок без подписи (для одинокой «Главной» сверху). */
export const PANEL_GROUPS = [
  { id: 'overview', label: null },
  { id: 'people',   label: 'Игроки' },
  { id: 'economy',  label: 'Экономика' },
  { id: 'content',  label: 'Контент' },
  { id: 'team',     label: 'Команда' },
  { id: 'insights', label: 'Аналитика' },
  { id: 'system',   label: 'Система' },
]

/** Секции, видимые с учётом прав и (опционально) матрицы panelSections с бэка. */
export function visibleSections(permissions = [], panelSections = null) {
  const perms = new Set(permissions)
  const allowedIds = Array.isArray(panelSections) && panelSections.length > 0
    ? new Set(panelSections)
    : null
  return PANEL_SECTIONS.filter((s) => {
    if (allowedIds && !allowedIds.has(s.id)) return false
    if (s.permission && !perms.has(s.permission)) return false
    return true
  })
}

/** Раскладывает секции по блокам сайдбара. Пустые блоки отбрасываются,
 *  иначе у админа с урезанными правами оставались бы висеть подписи
 *  групп без пунктов. */
export function groupSections(sections) {
  return PANEL_GROUPS
    .map((group) => ({
      ...group,
      items: sections.filter((s) => (s.group || 'system') === group.id),
    }))
    .filter((group) => group.items.length > 0)
}

export function getSectionById(id) {
  return PANEL_SECTIONS.find((s) => s.id === id) ?? PANEL_SECTIONS[0]
}
