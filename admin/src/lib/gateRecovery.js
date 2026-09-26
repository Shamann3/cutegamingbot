const STAFF_ROLES = new Set(['owner', 'senior_admin', 'junior_admin', 'moderator'])

/** Допуск по ответу /auth/status. Неполный ответ не закрывает двери наугад. */
export function portraitFrom(status) {
  const role = status?.role || null
  const accountStatus = status?.status || null
  const isOwner = Boolean(status?.isOwner)
  const staffCanEnter = status?.staffCanEnter ?? (isOwner || (accountStatus === 'active' && STAFF_ROLES.has(role)))
  const groups = Array.isArray(status?.groups) ? status.groups : []
  const groupCanEnter = status?.groupCanEnter ?? (isOwner || groups.length > 0)
  return {
    staffCanEnter: Boolean(staffCanEnter),
    groupCanEnter: Boolean(groupCanEnter),
    groups,
    isOwner,
    applicationStatus: status?.applicationStatus || null,
    accountStatus,
  }
}

/** Срок наказания в секундах. null — срок нельзя отправлять. */
export function punishmentHours(raw) {
  const n = Number(String(raw ?? '').trim().replace(',', '.'))
  if (!Number.isFinite(n) || n <= 0 || n > 24 * 366) return null
  return Math.round(n * 3600)
}
