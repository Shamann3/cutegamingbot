/** Общие константы и хелперы payroll UI */

export const SALARY_STATUS = {
  pending_approval: { label: 'ожидает', color: '#a1a1aa' },
  approved: { label: 'к выплате', color: '#d4d4d8' },
  partially_paid: { label: 'частично', color: '#a1a1aa' },
  paid: { label: 'выплачено', color: '#71717a' },
  cancelled: { label: 'снято', color: '#52525b' },
}

export const PERIOD_OPTIONS = [
  { value: 'day', label: 'День' },
  { value: 'week', label: 'Неделя' },
  { value: 'month', label: 'Месяц' },
  { value: 'year', label: 'Год' },
  { value: 'custom', label: 'Свои даты' },
]

export const SALARY_PAYOUT_OPTIONS = [
  { value: 'kut', label: 'Kut' },
  { value: 'stars', label: 'Stars' },
  { value: 'crypto', label: 'Крипта' },
  { value: 'card', label: 'Карта' },
  { value: 'other', label: 'Другое' },
]

export const ROLE_BADGE_COLOR = {
  owner: '#a78bfa',
  senior_admin: '#60a5fa',
  junior_admin: '#fbbf24',
  moderator: '#34d399',
  suspended: '#f87171',
}

export const ROLE_LABELS = {
  owner: 'Владелец',
  senior_admin: 'Старший',
  junior_admin: 'Младший',
  moderator: 'Модератор',
  suspended: 'Отстранён',
  applicant: 'Кандидат',
}

export function roleLabel(role) {
  return ROLE_LABELS[role] || role || '—'
}

export function nameOf(item) {
  if (!item) return '—'
  return item.firstName || (item.username ? `@${item.username}` : null) || `ID ${item.userId}`
}

export function fmtDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso.includes('T') ? iso : `${iso}T00:00:00`).toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', year: 'numeric',
    })
  } catch {
    return iso
  }
}

export function payoutLabel(value) {
  return SALARY_PAYOUT_OPTIONS.find((o) => o.value === value)?.label || value || '—'
}

/** Итог черновика — одна сумма (без коэффициентов). */
export function draftTotal(dft) {
  const n = Number.parseInt(dft?.amount ?? dft?.base, 10)
  return Number.isFinite(n) && n >= 0 ? n : 0
}

export function StatusBadge({ status }) {
  const st = SALARY_STATUS[status] || { label: status || 'не выставлено', color: '#71717a' }
  return (
    <span className="payroll-status" style={{ color: st.color }}>
      {st.label}
    </span>
  )
}
