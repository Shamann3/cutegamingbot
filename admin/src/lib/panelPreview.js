import { PANEL_SECTIONS, visibleSections } from '../constants/panelNav'

/** Копия панели для создателя: всё, что увидит сотрудник или администратор группы. */

// Без прав должности от сервера меню копии режет только список разделов.
export const PREVIEW_FALLBACK_PERMISSIONS = [...new Set(
  PANEL_SECTIONS.map((item) => item.permission).filter((item) => item && item !== 'manage_panel_access'),
)]

export function ruCount(n, one, few, many) {
  const value = Math.abs(Number(n) || 0)
  const tail = value % 100
  const last = value % 10
  const word = tail > 10 && tail < 20 ? many : last === 1 ? one : last >= 2 && last <= 4 ? few : many
  return `${value} ${word}`
}

export const STAFF_PUNISH_LABELS = {
  mute: 'Мут',
  muteall: 'Муталл',
  unmute: 'Размут',
  kick: 'Кик',
  kickall: 'Кикалл',
  warn: 'Варн',
  warnall: 'Варналл',
  warnfull: 'Варнфулл',
  ban: 'Бан',
  banall: 'Баналл',
  banfull: 'Банфулл',
}

export const GROUP_PUNISH_LABELS = {
  punish_mute: 'Мут',
  punish_voice: 'Голос',
  punish_kick: 'Кик',
  punish_warn: 'Варн',
  punish_ban: 'Бан',
}

export function previewAccessFromDefaults(map) {
  const sections = []
  const tabs = {}
  const source = map && typeof map === 'object' ? map : {}
  for (const [key, on] of Object.entries(source)) {
    const dot = key.indexOf('.')
    if (dot === -1) {
      if (on) sections.push(key)
      continue
    }
    const parent = key.slice(0, dot)
    const tab = key.slice(dot + 1)
    if (!tabs[parent]) tabs[parent] = []
    if (on) tabs[parent].push(tab)
  }
  return { sections, tabs }
}

/** Включённые наказания строки staff_rules. null — строки ещё не загружены. */
export function enabledPunish(rows, roleId) {
  if (!Array.isArray(rows)) return null
  const row = rows.find((item) => item.role === roleId)
  if (!row) return []
  return Object.entries(row.permissions || {})
    .filter(([, on]) => Boolean(on))
    .map(([key]) => String(key).trim().toLowerCase())
}

function personName(member) {
  const first = String(member?.firstName || '').trim()
  if (first) return first
  if (member?.username) return `@${member.username}`
  return `ID ${member?.userId ?? '—'}`
}

export function staffRolePreview(data, roleId, punishRows = null) {
  const role = (data?.roles || []).find((item) => item.id === roleId)
  const ready = data?.rolePreview?.[roleId] || null
  const access = ready || previewAccessFromDefaults(data?.roleDefaults?.[roleId] || {})
  return {
    kind: 'staff',
    who: 'role',
    role: roleId,
    roleLabel: role?.label || roleId,
    name: '',
    username: null,
    userId: null,
    sections: Array.isArray(access.sections) ? access.sections : [],
    tabs: access.tabs && typeof access.tabs === 'object' ? access.tabs : {},
    permissions: Array.isArray(ready?.permissions) ? ready.permissions : null,
    staffPerms: enabledPunish(punishRows, roleId),
  }
}

export function staffMemberPreview(member, punishRows = null) {
  return {
    kind: 'staff',
    who: 'person',
    role: member.role,
    roleLabel: member.roleLabel || member.role,
    name: personName(member),
    username: member.username || null,
    userId: member.userId ?? null,
    sections: Array.isArray(member.effectiveSections) ? member.effectiveSections : [],
    tabs: member.effectiveTabs && typeof member.effectiveTabs === 'object' ? member.effectiveTabs : {},
    permissions: Array.isArray(member.permissions) ? member.permissions : null,
    staffPerms: enabledPunish(punishRows, member.role),
  }
}

/** Меню ровно так, как его соберёт панель этого сотрудника. */
export function staffPreviewNav(preview, projectCreatorId = null) {
  if (!preview) return []
  return visibleSections(
    preview.permissions || PREVIEW_FALLBACK_PERMISSIONS,
    preview.sections,
    preview.role,
    { myUserId: preview.userId, projectCreatorId, isProjectCreator: false },
  )
}

export const CABINET_PAGE_DEFS = [
  { id: 'work', label: 'Работа', hint: 'Проверка наказаний. В нижней полосе, рядом с Главной.' },
  { id: 'archive', label: 'Архив', hint: 'Карточки наказаний этой группы.' },
  { id: 'activity', label: 'Активность', hint: 'Кто писал и сколько сообщений.' },
  { id: 'rights', label: 'Права', hint: 'Должности младше своей. Новую создаёт только создатель.' },
  { id: 'pay', label: 'Моя зарплата', hint: 'Сколько дел осталось до суммы и как забрать уже набранное.' },
]

function placePay(items) {
  const rest = items.filter((item) => item.id !== 'pay' && item.id !== 'more')
  const more = items.filter((item) => item.id === 'more')
  const workAt = rest.findIndex((item) => item.id === 'work')
  const next = rest.slice()
  next.splice(workAt >= 0 ? workAt + 1 : Math.min(1, next.length), 0, { id: 'pay', label: 'Моя зарплата' })
  return [...next, ...more]
}

const CABINET_PAGE_IDS = CABINET_PAGE_DEFS.map((item) => item.id)

export function groupCabinetTabs(rights, isCreator = false, pages, rank = 0) {
  if (isCreator) {
    return placePay([
      { id: 'overview', label: 'Главная' },
      { id: 'work', label: 'Работа' },
      { id: 'archive', label: 'Архив' },
      { id: 'activity', label: 'Активность' },
      { id: 'rights', label: 'Должности' },
      { id: 'switches', label: 'Переключатели' },
      { id: 'more', label: 'Ещё' },
    ])
  }
  const items = [{ id: 'overview', label: 'Главная' }]
  if (Array.isArray(pages)) {
    const chosen = new Set(pages)
    for (const item of CABINET_PAGE_DEFS) {
      if (chosen.has(item.id)) items.push({ id: item.id, label: item.label })
    }
    items.push({ id: 'more', label: 'Ещё' })
    return placePay(items)
  }
  if (Number(rank) >= 5) {
    return placePay([
      { id: 'overview', label: 'Главная' },
      ...CABINET_PAGE_DEFS.filter((item) => item.id !== 'pay').map((item) => ({ id: item.id, label: item.label })),
      { id: 'more', label: 'Ещё' },
    ])
  }
  const set = rights instanceof Set ? rights : new Set(rights || [])
  const has = (key) => set.has(key)
  if (has('view_archive')) items.push({ id: 'work', label: 'Работа' })
  if (has('view_archive')) items.push({ id: 'archive', label: 'Архив' })
  if (has('view_members') || has('view_analytics') || [...set].some((item) => item.startsWith('punish_'))) {
    items.push({ id: 'activity', label: 'Активность' })
  }
  if (has('manage_positions')) items.push({ id: 'rights', label: 'Должности' })
  items.push({ id: 'more', label: 'Ещё' })
  return placePay(items)
}

export function derivedCabinetPageIds(rights) {
  return groupCabinetTabs(rights, false)
    .map((item) => item.id)
    .filter((id) => CABINET_PAGE_IDS.includes(id))
}

export function cabinetPagesFor(row) {
  if (Array.isArray(row?.pages)) {
    const chosen = new Set(row.pages)
    return CABINET_PAGE_IDS.filter((id) => chosen.has(id))
  }
  if (Number(row?.rank) >= 5) return [...CABINET_PAGE_IDS]
  return derivedCabinetPageIds(row?.rights)
}

export function positionSaveBody(row) {
  return {
    title: String(row?.title || '').trim(),
    rights: Array.isArray(row?.rights) ? row.rights : [],
    pages: cabinetPagesFor(row),
  }
}

function seatGroup(group, post) {
  return {
    chatId: group.chatId,
    title: group.title || String(group.chatId),
    username: group.username || '',
    position: post.title || post.position || '',
    rank: Number(post.rank) || 0,
    rights: Array.isArray(post.rights) ? post.rights : [],
    ...(Array.isArray(post.pages) ? { pages: post.pages } : {}),
  }
}

function byRankThenTitle(a, b) {
  return (b.rank - a.rank) || String(a.title).localeCompare(String(b.title), 'ru')
}

export function groupPositionPreview(group, position) {
  return {
    kind: 'group',
    who: 'role',
    roleLabel: position.title || 'Должность',
    name: '',
    username: null,
    userId: null,
    portrait: { isOwner: false, staffCanEnter: false, groups: [seatGroup(group, position)] },
  }
}

/** Люди на должностях во всех официальных группах, каждый один раз. */
export function groupPeople(boardGroups) {
  const people = new Map()
  for (const group of boardGroups || []) {
    for (const seat of group.seats || []) {
      const id = Number(seat.userId)
      const entry = people.get(id) || {
        userId: id,
        name: seat.name || `ID ${id}`,
        username: seat.username || '',
        staff: Boolean(seat.staff),
        groups: [],
      }
      entry.groups.push(seatGroup(group, seat))
      people.set(id, entry)
    }
  }
  const list = [...people.values()]
  for (const person of list) person.groups.sort(byRankThenTitle)
  return list.sort((a, b) => ((b.groups[0]?.rank || 0) - (a.groups[0]?.rank || 0)) || a.name.localeCompare(b.name, 'ru'))
}

export function groupPersonPreview(person) {
  return {
    kind: 'group',
    who: 'person',
    roleLabel: person.groups[0]?.position || 'Администратор',
    name: person.name,
    username: person.username || null,
    userId: person.userId,
    portrait: { isOwner: false, staffCanEnter: Boolean(person.staff), groups: person.groups },
  }
}

export function previewTitle(preview) {
  if (!preview) return ''
  const where = preview.kind === 'group' ? 'Копия кабинета группы' : 'Копия панели сотрудника'
  if (preview.who === 'person') {
    const role = preview.kind === 'staff' && preview.roleLabel ? ` (${preview.roleLabel})` : ''
    return `${where} · ${preview.name}${role}`
  }
  return `${where} · ${preview.roleLabel}`
}

export function previewStandIn(preview) {
  if (!preview) return null
  if (preview.who === 'person') {
    return { displayName: preview.name, username: preview.username, userId: preview.userId }
  }
  return { displayName: preview.roleLabel, username: null, userId: null }
}
