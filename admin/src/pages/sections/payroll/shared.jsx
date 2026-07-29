/** Общие константы и хелперы payroll UI */

export const SALARY_STATUS = {
  pending_approval: { label: 'ожидает одобрения', color: '#fbbf24' },
  approved: { label: 'одобрено', color: '#fb923c' },
  partially_paid: { label: 'частично', color: '#60a5fa' },
  paid: { label: 'выплачено', color: '#34d399' },
  cancelled: { label: 'снято', color: '#94a3b8' },
}

export const PERIOD_OPTIONS = [
  { value: 'day', label: 'День' },
  { value: 'week', label: 'Неделя' },
  { value: 'month', label: 'Месяц' },
  { value: 'year', label: 'Год' },
]

export const SALARY_PAYOUT_OPTIONS = [
  { value: 'kut', label: 'Kut → игровой баланс' },
  { value: 'stars', label: 'Telegram Stars' },
  { value: 'crypto', label: 'Крипта' },
  { value: 'card', label: 'Карта / СБП' },
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

export function draftTotal(dft) {
  const base = Number.parseInt(dft?.base, 10) || 0
  const coeff = Number.parseFloat(dft?.coefficient) || 0
  const bonus = Number.parseInt(dft?.bonus, 10) || 0
  const penalty = Number.parseInt(dft?.penalty, 10) || 0
  return Math.max(0, Math.round(base * coeff) + bonus - penalty)
}

export function StatusBadge({ status }) {
  const st = SALARY_STATUS[status] || { label: status || '—', color: '#94a3b8' }
  return (
    <span className="staff-badge" style={{ '--badge-color': st.color }}>
      {st.label}
    </span>
  )
}
