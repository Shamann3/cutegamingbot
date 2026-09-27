/** Действия модерации стаффа и нужный столбец staff_rules / флаг панели. */

export const STAFF_PUNISH_GROUPS = [
  {
    group: 'В этой группе',
    items: [
      { id: 'mute', label: '🔇 Мут', needsUntil: true, perm: 'mute' },
      { id: 'unmute', label: '🔊 Размут', needsUntil: false, perm: 'unmute' },
      { id: 'kick', label: '👋 Кик', needsUntil: false, perm: 'kick' },
      { id: 'warn', label: '⚠️ Варн', needsUntil: true, perm: 'warn' },
      { id: 'ban', label: '🚫 Бан', needsUntil: true, perm: 'ban' },
      { id: 'unban', label: '✅ Разбан', needsUntil: false, perm: 'ban' },
    ],
  },
  {
    group: 'Во всех официальных группах',
    items: [
      { id: 'muteall', label: '🔇 Муталл', needsUntil: true, perm: 'muteall' },
      { id: 'unmuteall', label: '🔊 Размуталл', needsUntil: false, perm: 'muteall' },
      { id: 'warnall', label: '⚠️ Варналл', needsUntil: true, perm: 'warnall' },
      { id: 'banall', label: '🚫 Баналл', needsUntil: true, perm: 'banall' },
      { id: 'unbanall', label: '✅ Разбаналл', needsUntil: false, perm: 'banall' },
    ],
  },
  {
    group: 'Весь проект',
    items: [
      { id: 'warnfull', label: '⚠️ Варнфулл', needsUntil: true, perm: 'warnfull' },
      { id: 'banfull', label: 'Запрет на весь проект', needsUntil: true, perm: 'banfull' },
      { id: 'bot_ban', label: '🤖 Бан в боте', needsUntil: false, perm: 'ban' },
      { id: 'bot_unban', label: '🤖 Разбан в боте', needsUntil: false, perm: 'ban' },
    ],
  },
]

const SELF_BAN_ACTIONS = new Set(['ban', 'banall', 'banfull', 'bot_ban', 'mute', 'muteall', 'kick', 'warn', 'warnall', 'warnfull'])

/** Owner / создатель проекта видит все действия. */
export function isModerationSuper({ role = null, isProjectCreator = false } = {}) {
  return role === 'owner' || !!isProjectCreator
}

/**
 * Фильтр групп наказаний по правам.
 * @param {object} opts
 * @param {boolean} [opts.canBanfull]
 * @param {string[]} [opts.permissions] — API-права панели (moderate_ban и т.п.)
 * @param {Set<string>|string[]|null} [opts.staffPerms] — столбцы staff_rules (mute, banfull…)
 * @param {string|null} [opts.role]
 * @param {boolean} [opts.isProjectCreator]
 */
export function filterStaffPunishGroups({
  canBanfull = false,
  permissions = [],
  staffPerms = null,
  role = null,
  isProjectCreator = false,
} = {}) {
  if (isModerationSuper({ role, isProjectCreator })) return STAFF_PUNISH_GROUPS

  const panel = new Set(permissions || [])
  const staff = staffPerms == null
    ? null
    : staffPerms instanceof Set
      ? staffPerms
      : new Set(staffPerms)

  const hasStaff = (col) => {
    if (col === 'banfull') return !!canBanfull || (staff ? staff.has('banfull') : false)
    if (staff) return staff.has(col)
    // Без явной матрицы staff_rules: базовые действия — при moderate_ban; banfull только по флагу.
    if (col === 'banfull') return !!canBanfull
    if (['mute', 'unmute', 'kick', 'warn', 'ban'].includes(col)) {
      return panel.has('moderate_ban') || panel.has('moderate_unban')
    }
    // muteall / banall / warn* — только если есть явный staff-perm или super
    return false
  }

  return STAFF_PUNISH_GROUPS
    .map((g) => ({
      ...g,
      items: g.items.filter((item) => hasStaff(item.perm)),
    }))
    .filter((g) => g.items.length > 0)
}

export function isSelfModerationTarget(actorId, targetId) {
  if (actorId == null || targetId == null) return false
  return Number(actorId) === Number(targetId)
}

export function selfBanBlocked(action, actorId, targetId) {
  if (!SELF_BAN_ACTIONS.has(action)) return null
  if (!isSelfModerationTarget(actorId, targetId)) return null
  return 'Вы не можете заблокировать самого себя'
}
