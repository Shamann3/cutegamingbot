/** Куда поставить наказание, которое только что появилось. Первая загрузка — не «новое». */

const HERE = {
  mute: 'Новый мут уже в этом списке.',
  unmute: 'Снятие мута уже в этом списке.',
  ban: 'Новый бан уже в этом списке.',
  unban: 'Снятие бана уже в этом списке.',
  kick: 'Новый кик уже в этом списке.',
  warn: 'Новое предупреждение уже в этом списке.',
  unwarn: 'Снятие предупреждения уже в этом списке.',
  voice: 'Запрет голоса уже в этом списке.',
  unvoice: 'Возврат голоса уже в этом списке.',
}

const HIDDEN = {
  mute: 'Новый мут уже в архиве. Этот фильтр его не показывает.',
  unmute: 'Снятие мута уже в архиве. Этот фильтр его не показывает.',
  ban: 'Новый бан уже в архиве. Этот фильтр его не показывает.',
  unban: 'Снятие бана уже в архиве. Этот фильтр его не показывает.',
  kick: 'Новый кик уже в архиве. Этот фильтр его не показывает.',
  warn: 'Новое предупреждение уже в архиве. Этот фильтр его не показывает.',
  unwarn: 'Снятие предупреждения уже в архиве. Этот фильтр его не показывает.',
  voice: 'Запрет голоса уже в архиве. Этот фильтр его не показывает.',
  unvoice: 'Возврат голоса уже в архиве. Этот фильтр его не показывает.',
}

export function kindOf(row) {
  return String(row?.action || row?.actionType || '').toLowerCase()
}

export function arrivalLine(rows) {
  const list = Array.isArray(rows) ? rows.filter(Boolean) : []
  if (!list.length) return ''
  if (list.length > 1) return `В этот список добавлено ${list.length}.`
  return HERE[kindOf(list[0])] || 'Новая запись уже в этом списке.'
}

export function hiddenLine(row) {
  return HIDDEN[kindOf(row)] || 'Новая запись уже в архиве. Этот фильтр её не показывает.'
}

export function pileLine(extra) {
  const count = Number(extra) || 0
  if (count <= 0) return ''
  if (count === 1) return 'Пока эта карточка открыта, новое наказание уже в колоде.'
  return `Пока эта карточка открыта, в колоду пришло ещё ${count}.`
}

export function watchKey(watch) {
  if (!Array.isArray(watch)) return ''
  return watch.map((person) => `${person.userId}:${person.warns}`).join('|')
}

export function samePulse(moderation, pulse) {
  if (!moderation || !pulse) return false
  const keys = ['actions30d', 'mutes', 'bans', 'warns', 'kicks']
  for (const key of keys) {
    if (Number(moderation[key]) !== Number(pulse[key])) return false
  }
  const left = moderation.captchaRemoved
  const right = pulse.captchaRemoved
  if (right && !left) return false
  if (left && right) {
    if (Number(left.people) !== Number(right.people)) return false
    if (Number(left.month) !== Number(right.month)) return false
    if (Number(left.active) !== Number(right.active)) return false
  }
  return watchKey(moderation.watch) === watchKey(pulse.watch)
}

export function moderationDelta(previousRecent, incomingRecent) {
  const next = Array.isArray(incomingRecent) ? incomingRecent : []
  if (!Array.isArray(previousRecent)) return { fresh: [], changed: false, recent: next }
  const prevById = new Map(previousRecent.map((row) => [Number(row.id), row]))
  const fresh = []
  let changed = previousRecent.length !== next.length
  for (const row of next) {
    const id = Number(row?.id)
    const old = id ? prevById.get(id) : null
    if (!old) {
      if (id) fresh.push(row)
      changed = true
      continue
    }
    if (old.sortVerdict !== row.sortVerdict || old.reason !== row.reason) changed = true
  }
  return { fresh, changed, recent: next }
}

/** Дата — сверху. Тип — в начало своей группы, список вкладок не меняется. */
export function placeLogs(items, incoming, sortBy) {
  const list = Array.isArray(items) ? items.slice() : []
  const known = new Set(list.map((row) => Number(row.id)))
  const fresh = (incoming || []).filter((row) => row?.id && !known.has(Number(row.id)))
  if (!fresh.length) return { fresh: [], items: list }
  if (sortBy === 'type') {
    const next = list.slice()
    const ordered = [...fresh].sort((a, b) => (
      String(a.actionType || '').localeCompare(String(b.actionType || '')) || Number(b.id) - Number(a.id)
    ))
    for (const row of ordered) {
      const type = String(row.actionType || '')
      let at = next.findIndex((item) => String(item.actionType) === type)
      if (at === -1) {
        at = next.findIndex((item) => String(item.actionType) > type)
        if (at === -1) at = next.length
      }
      next.splice(at, 0, row)
    }
    return { fresh, items: next }
  }
  const ordered = [...fresh].sort((a, b) => Number(b.id) - Number(a.id))
  return { fresh, items: [...ordered, ...list] }
}
