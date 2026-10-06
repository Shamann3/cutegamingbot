import { spanToSend, speakSpan } from './spanClock'

/** Наказание из панели сотрудника. Список действий присылает сервер — по правам должности. */

export const PUNISH_SCOPES = [
  { id: 'chat', title: 'В выбранной группе' },
  { id: 'all', title: 'Во всех официальных группах' },
  { id: 'full', title: 'Во всём проекте' },
]

const LIFTS = new Set(['unmute', 'unban', 'unmuteall', 'unbanall'])

export function isLift(actionId) {
  return LIFTS.has(String(actionId || ''))
}

export function punishShelves(actions) {
  const list = Array.isArray(actions) ? actions.filter((item) => item?.id) : []
  return PUNISH_SCOPES
    .map((scope) => ({ ...scope, items: list.filter((item) => (item.scope || 'chat') === scope.id) }))
    .filter((shelf) => shelf.items.length > 0)
}

export function punishProblem({ action, chatId, spanSec, reason, actorId, targetId }) {
  if (!action) return 'Выберите наказание'
  if (chatId === '' || chatId == null) return 'Выберите группу'
  if (action.needsUntil && spanToSend(spanSec) == null) return 'Укажите срок больше нуля и не дольше 366 дней'
  if (String(reason || '').trim().length < 2) return 'Напишите причину'
  if (actorId != null && targetId != null && Number(actorId) === Number(targetId)) {
    return isLift(action.id) ? 'Снять наказание с самого себя нельзя' : 'Себя наказать нельзя'
  }
  return ''
}

export function punishVerb(action, spanSec) {
  if (!action) return 'Выдать'
  if (isLift(action.id)) return action.label
  const sent = action.needsUntil ? spanToSend(spanSec) : null
  return sent ? `Выдать: ${action.label} · ${speakSpan(sent)}` : `Выдать: ${action.label}`
}

export function punishReceipt(result) {
  if (!result?.label) return ''
  const place = result.scope === 'full'
    ? 'весь проект'
    : result.scope === 'all'
      ? 'все официальные группы'
      : `«${result.chatTitle}»`
  const span = result.untilSec ? speakSpan(result.untilSec) : ''
  return [result.label, place, span].filter(Boolean).join(' · ')
}
