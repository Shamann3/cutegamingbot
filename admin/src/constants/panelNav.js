/** Разделы admin-панели. id = ключ экрана, group = блок в сайдбаре. */

export const PANEL_SECTIONS = [
  {
    id: 'dashboard', label: 'Dashboard', labelRu: 'Главная', group: 'overview',
    blurb: 'Обзор панели: статус сервера, быстрые метрики и входная точка.',
  },
  {
    id: 'users', label: 'Players', labelRu: 'Игроки', group: 'people', permission: 'view_players',
    blurb: 'Поиск игроков, профиль, баланс, предметы, баны и правки аккаунта.',
  },
  {
    id: 'accounts', label: 'Accounts', labelRu: 'Пользователи', group: 'people', permission: 'view_accounts',
    blurb: 'Чувствительный список аккаунтов: регистрации, связки и обзор базы.',
  },
  {
    id: 'moderation', label: 'Moderation', labelRu: 'Архив', group: 'people',
    blurb: 'Архив модерации: логи банов, апелляции и история действий.',
  },
  {
    id: 'economy', label: 'Economy', labelRu: 'Экономика', group: 'economy', permission: 'manage_economy',
    blurb: 'Настройка экономики игры: цены, курсы и экономические параметры.',
  },
  {
    id: 'market', label: 'Market', labelRu: 'Биржа', group: 'economy', permission: 'view_market',
    blurb: 'Биржа игроков: лоты, отмена сделок и контроль рынка.',
  },
  {
    id: 'farm', label: 'Farm Management', labelRu: 'Ферма', group: 'economy', permission: 'manage_farm',
    blurb: 'Управление фермой: культуры, грядки, рост и связанные механики.',
  },
  {
    id: 'content', label: 'Content', labelRu: 'Контент', group: 'content', permission: 'manage_content',
    blurb: 'Игровой контент: предметы, крафт, квесты и карта крафта.',
  },
  {
    id: 'giveaways', label: 'Giveaways', labelRu: 'Розыгрыши', group: 'content', permission: 'manage_content',
    blurb: 'Создание и контроль розыгрышей призов для игроков.',
  },
  {
    id: 'events', label: 'Events', labelRu: 'Ивенты', group: 'content', permission: 'manage_events',
    blurb: 'Игровые ивенты: запуск, расписание и параметры активностей.',
  },
  {
    id: 'broadcast', label: 'Broadcast', labelRu: 'Рассылка', group: 'content', permission: 'manage_broadcast',
    blurb: 'Массовые сообщения игрокам: тексты, фильтры и планирование.',
  },
  {
    id: 'staff', label: 'Staff', labelRu: 'Стафф', group: 'team',
    blurb: 'Команда: заявки, сотрудники, зарплаты, смены и жалобы.',
  },
  {
    id: 'support', label: 'Support', labelRu: 'Поддержка', group: 'team',
    blurb: 'Тикеты поддержки: переписка с игроками и статусы обращений.',
  },
  {
    id: 'analytics', label: 'Analytics', labelRu: 'Аналитика', group: 'insights', permission: 'view_analytics',
    blurb: 'Сводная аналитика: онлайн, активность и ключевые показатели.',
  },
  {
    id: 'logs', label: 'Logs', labelRu: 'Логи', group: 'insights', permission: 'view_logs',
    blurb: 'Системные и админ-логи для разбора инцидентов.',
  },
  {
    id: 'chronicle', label: 'Chronicle', labelRu: 'Хронология', group: 'insights',
    blurb: 'Лента событий по проекту: что происходило и когда.',
  },
  {
    id: 'settings', label: 'Settings', labelRu: 'Настройки', group: 'system', permission: 'manage_settings',
    blurb: 'Системные настройки панели и игры, режим обслуживания.',
  },
  {
    id: 'security', label: 'Security', labelRu: 'Доступ', group: 'system', permission: 'manage_security',
    blurb: 'Безопасность: аудит действий, IP-баны и сессии 2FA.',
  },
  {
    id: 'panelAccess', label: 'Admin Panel', labelRu: 'Админ панель', group: 'system', permission: 'manage_panel_access',
    blurb: 'Матрица доступов к вкладкам панели — только для владельца.',
  },
]

/** Короткое описание раздела для матрицы доступов. */
export function sectionBlurb(id) {
  return PANEL_SECTIONS.find((s) => s.id === id)?.blurb || ''
}

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
