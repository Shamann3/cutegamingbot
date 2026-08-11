/** Дерево доступов: основные разделы → внутренние вкладки.
 *  Ключи детей в API: `${parentId}.${tabId}` (например staff.salaries).
 */

import { PANEL_SECTIONS, sectionBlurb } from './panelNav'

/** @typedef {{ id: string, label: string, blurb: string, ownerOnly?: boolean, selfOnly?: boolean }} AccessTab */

/** @type {Record<string, AccessTab[]>} */
export const PANEL_SECTION_TABS = {
  staff: [
    { id: 'applications', label: 'Заявки', blurb: 'Просмотр и разбор заявок кандидатов в команду.' },
    { id: 'members', label: 'Сотрудники', blurb: 'Список сотрудников, роли, статусы и карточки.' },
    { id: 'invites', label: 'Инвайты', blurb: 'Создание инвайт-ссылок для найма.' },
    { id: 'salaries', label: 'Зарплаты', blurb: 'Выставление и сохранение зарплат, отправка Stars в канал.' },
    { id: 'bonuses', label: 'Премии', blurb: 'Премии сотрудникам поверх основной зарплаты.' },
    { id: 'ledger', label: 'Реестр', blurb: 'Реестр выплат и подтверждения крупных сумм.' },
    { id: 'payoutsettings', label: 'Настройки выплат', blurb: 'Пороги, способы и правила выплат.', ownerOnly: true },
    { id: 'leaderboard', label: 'Отчёты', blurb: 'Отчёты и рейтинг активности стаффа.' },
    { id: 'shifts', label: 'Смены', blurb: 'Расписание смен сотрудников.' },
    { id: 'complaints', label: 'Жалобы', blurb: 'Жалобы на сотрудников и разбор.' },
    { id: 'questions', label: 'Анкета', blurb: 'Вопросы анкеты при регистрации стаффа.' },
    { id: 'mysalary', label: 'Моя зарплата', blurb: 'Личная зарплата сотрудника (не для владельца).', selfOnly: true },
    { id: 'mycomplaints', label: 'Жалобы на меня', blurb: 'Жалобы, где сотрудник — ответчик.', selfOnly: true },
  ],
  content: [
    { id: 'items', label: 'Предметы', blurb: 'Каталог предметов и их параметры.' },
    { id: 'crops', label: 'Культуры', blurb: 'Культуры фермы, рост и дропы.' },
    { id: 'craft', label: 'Крафт', blurb: 'Рецепты крафта и связки предметов.' },
    { id: 'map', label: 'Карта', blurb: 'Визуальная карта крафта (обычно только владелец).', ownerOnly: true },
    { id: 'quests', label: 'Задания', blurb: 'Игровые квесты и награды.' },
  ],
  moderation: [
    { id: 'archive', label: 'Архив', blurb: 'Архив модерационных действий.' },
    { id: 'appeals', label: 'Апелляции', blurb: 'Разбор апелляций по банам.' },
    { id: 'stats', label: 'Статистика', blurb: 'Статистика модераторов.' },
  ],
  security: [
    { id: 'audit', label: 'Аудит', blurb: 'Журнал действий администраторов.' },
    { id: 'ipbans', label: 'IP-баны', blurb: 'Блокировки по IP.' },
    { id: 'sessions', label: 'Сессии', blurb: 'Сессии и принудительный перелогин 2FA.' },
  ],
  settings: [
    { id: 'seed', label: 'Семена', blurb: 'Игровые настройки семян и экономики старта.' },
    { id: 'system', label: 'Система', blurb: 'Системные флаги и обслуживание.' },
    { id: 'history', label: 'История', blurb: 'История изменений настроек.' },
  ],
  events: [
    { id: 'timeline', label: 'Расписание', blurb: 'Календарь и таймлайн ивентов.' },
    { id: 'quests', label: 'Ивент-квесты', blurb: 'Квесты, привязанные к ивентам.' },
    { id: 'broadcasts', label: 'Рассылки', blurb: 'Рассылки в рамках ивентов.' },
  ],
  broadcast: [
    { id: 'players', label: 'Игрокам', blurb: 'Массовая рассылка игрокам.' },
    { id: 'groups', label: 'В группы', blurb: 'Посты в Telegram-группы.' },
  ],
  analytics: [
    { id: 'quests', label: 'Квесты', blurb: 'Аналитика по квестам.' },
    { id: 'farm', label: 'Ферма', blurb: 'Аналитика фермы.' },
    { id: 'market', label: 'Биржа', blurb: 'Аналитика биржи.' },
    { id: 'craft', label: 'Крафт', blurb: 'Аналитика крафта.' },
    { id: 'retention', label: 'Удержание', blurb: 'Удержание и возвращаемость игроков.' },
  ],
  logs: [
    { id: 'audit', label: 'Audit', blurb: 'Аудит-логи системы.' },
    { id: 'transfers', label: 'Переводы', blurb: 'Логи переводов и P2P.' },
    { id: 'security', label: 'Security', blurb: 'Логи безопасности.' },
    { id: 'errors', label: 'Сбои', blurb: 'Ошибки и сбои сервисов.' },
  ],
}

export function childKey(parentId, tabId) {
  return `${parentId}.${tabId}`
}

export function parseAccessKey(key) {
  const i = String(key || '').indexOf('.')
  if (i < 0) return { parentId: key, tabId: null }
  return { parentId: key.slice(0, i), tabId: key.slice(i + 1) }
}

/** Плоский список настраиваемых ключей (родители + дети). */
export function allConfigurableKeys(includeOwnerOnlyParents = false) {
  const keys = []
  for (const s of PANEL_SECTIONS) {
    if (s.id === 'panelAccess' && !includeOwnerOnlyParents) continue
    keys.push(s.id)
    const tabs = PANEL_SECTION_TABS[s.id] || []
    for (const t of tabs) {
      if (t.ownerOnly) continue // owner-only tabs не в дефолтах ролей
      keys.push(childKey(s.id, t.id))
    }
  }
  return keys
}

export function tabsForSection(sectionId) {
  return PANEL_SECTION_TABS[sectionId] || []
}

export function hasChildren(sectionId) {
  return (PANEL_SECTION_TABS[sectionId] || []).length > 0
}

/** Фильтр внутренних вкладок секции по panelTabs с /auth/me. */
export function filterSectionTabs(sectionId, tabs, panelTabs) {
  if (!Array.isArray(tabs) || !tabs.length) return tabs || []
  if (panelTabs == null) return tabs
  const allowed = panelTabs[sectionId]
  if (!Array.isArray(allowed)) return tabs
  const set = new Set(allowed)
  return tabs.filter((t) => set.has(t.id))
}

/** Слайды для «Простой настройки»: каждый основной раздел. */
export function wizardSlides() {
  return PANEL_SECTIONS
    .filter((s) => s.id !== 'panelAccess' && !s.ownerOnly)
    .map((s) => ({
      id: s.id,
      label: s.labelRu,
      blurb: sectionBlurb(s.id) || s.blurb || '',
      tabs: (PANEL_SECTION_TABS[s.id] || []).filter((t) => !t.ownerOnly),
    }))
}
