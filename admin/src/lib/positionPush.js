import { CABINET_PAGE_DEFS, ruCount } from './panelPreview'
import { positionOrder } from './rankLadder'
import { REALM_RIGHTS } from './realmRights'

/** Перенос должностей в другую группу. Те же правила, что у сервера: превью не обещает лишнего. */

const KINDS = new Set(['post', 'member', 'spamblock'])
const STAFF_TOP = 4
const SPAMBLOCK_PREFIX = 'спам блок'
const PAGE_IDS = ['work', 'archive', 'activity', 'rights', 'pay']

export const PUSH_OWNER_REASON = 'Создатель группы в каждой группе свой и не переносится'
export const PUSH_TWIN_REASON = 'В этом переносе две должности с таким названием'
export const PUSH_GONE_REASON = 'Этой должности здесь уже нет'

const RIGHT_LABELS = new Map(REALM_RIGHTS.map((item) => [item.id, item.label]))
const PAGE_LABELS = new Map(CABINET_PAGE_DEFS.map((item) => [item.id, item.label]))

function clean(value) {
  return String(value ?? '').trim().replace(/\s+/g, ' ')
}

function nameKey(value) {
  return clean(value).toLowerCase()
}

export function pushKey(row) {
  const kind = KINDS.has(row?.kind) ? row.kind : 'post'
  return kind === 'post' ? `title:${nameKey(row?.title)}` : `kind:${kind}`
}

/** Вкладки, которые должность видит на деле. Без своего списка они идут от прав. */
export function pushPages(rights, pages) {
  if (Array.isArray(pages)) return new Set(pages.filter((id) => PAGE_IDS.includes(id)))
  const have = new Set(rights || [])
  const open = new Set()
  if (have.has('view_archive')) {
    open.add('work')
    open.add('archive')
  }
  if (have.has('view_members') || have.has('view_analytics') || [...have].some((id) => String(id).startsWith('punish_'))) {
    open.add('activity')
  }
  if (have.has('manage_positions')) open.add('rights')
  return open
}

function shape(row) {
  const kind = KINDS.has(row?.kind) ? row.kind : 'post'
  let prefix = clean(row?.prefix).slice(0, 16)
  if (kind === 'spamblock' && !prefix) prefix = SPAMBLOCK_PREFIX
  return {
    id: Number(row?.id) || 0,
    title: clean(row?.title),
    kind,
    rank: Number(row?.rank) || 0,
    ladder: Number(row?.ladder) || 0,
    rights: [...new Set((row?.rights || []).map(String))],
    pages: Array.isArray(row?.pages) ? PAGE_IDS.filter((id) => row.pages.includes(id)) : null,
    prefix,
    accepting: kind === 'post' ? Boolean(row?.accepting) : false,
  }
}

function clashReason(row) {
  if (!row) return PUSH_TWIN_REASON
  if (row.rank >= 5) return 'Так в той группе называется создатель группы'
  if (row.kind === 'member') return 'Так в той группе называется обычный пользователь'
  if (row.kind === 'spamblock') return 'Так в той группе называется спам-блок'
  return 'Такое название в той группе уже занято'
}

function skip(row, reason) {
  return { sourceId: row.id, title: row.title || 'Должность', kind: row.kind, state: 'skip', reason }
}

/** Перенесённая встаёт под теми, кто здесь выше неё. Без общих должностей решает ранг отсюда. */
function pushLine(sourceStaff, targetStaff, movingOld, movingNew) {
  const sourceIndex = new Map(sourceStaff.map((row, index) => [row.id, index]))
  const sourceByName = new Map()
  sourceStaff.forEach((row, index) => {
    const name = nameKey(row.title)
    if (!sourceByName.has(name)) sourceByName.set(name, index)
  })
  const anchor = new Map()
  const rankOf = new Map()
  const line = []
  for (const row of targetStaff) {
    const slot = `old:${row.id}`
    rankOf.set(slot, row.rank)
    if (movingOld.has(row.id)) continue
    line.push(slot)
    const at = sourceByName.get(nameKey(row.title))
    if (at !== undefined) anchor.set(slot, at)
  }
  const movers = [
    ...[...movingOld.entries()].map(([targetId, row]) => ({ index: sourceIndex.get(row.id), slot: `old:${targetId}`, want: row.rank })),
    ...movingNew.map((row) => ({ index: sourceIndex.get(row.id), slot: `new:${row.id}`, want: row.rank })),
  ].sort((a, b) => a.index - b.index)
  for (const mover of movers) {
    let place = -1
    line.forEach((slot, pos) => {
      const seen = anchor.get(slot)
      if (seen !== undefined && seen < mover.index) place = pos + 1
    })
    if (place < 0) {
      place = line.findIndex((slot) => {
        const seen = anchor.get(slot)
        return seen !== undefined && seen > mover.index
      })
    }
    if (place < 0) {
      const lower = line.findIndex((slot) => (rankOf.get(slot) ?? 0) < mover.want)
      place = lower >= 0 ? lower : line.length
    }
    line.splice(place, 0, mover.slot)
    anchor.set(mover.slot, mover.index)
    rankOf.set(mover.slot, mover.want)
  }
  return line
}

/**
 * Что станет с должностями другой группы. Ничего не пишет.
 * items — в порядке лестницы отсюда: new, update, same или skip.
 * shifts — должности той группы, у которых сдвинется ранг.
 */
export function planPush({ source = [], target = [], ids = [] } = {}) {
  const src = positionOrder((source || []).map(shape))
  const tgt = positionOrder((target || []).map(shape))
  const byId = new Map(src.map((row) => [row.id, row]))
  const wanted = []
  for (const raw of ids || []) {
    const id = Number(raw)
    if (id > 0 && !wanted.includes(id)) wanted.push(id)
  }
  const gone = wanted
    .filter((id) => !byId.has(id))
    .map((id) => ({ sourceId: id, title: 'Должность', kind: 'post', state: 'skip', reason: PUSH_GONE_REASON }))
  const picked = new Set(wanted)
  const chosen = src.filter((row) => picked.has(row.id))
  const byKey = new Map()
  const byTitle = new Map()
  for (const row of tgt) {
    const name = nameKey(row.title)
    if (!byTitle.has(name)) byTitle.set(name, row)
    if (row.rank < 5) {
      const key = pushKey(row)
      if (!byKey.has(key)) byKey.set(key, row)
    }
  }
  const claimed = new Set()
  const names = new Set()
  const create = []
  const matched = []
  const items = new Map()
  for (const row of chosen) {
    if (row.rank >= 5) {
      items.set(row.id, skip(row, PUSH_OWNER_REASON))
      continue
    }
    const name = nameKey(row.title)
    const match = byKey.get(pushKey(row))
    if (match && claimed.has(match.id)) {
      items.set(row.id, skip(row, PUSH_TWIN_REASON))
      continue
    }
    if (!match) {
      if (byTitle.has(name) || names.has(name)) {
        items.set(row.id, skip(row, clashReason(byTitle.get(name))))
        continue
      }
      if (row.title.length < 2) {
        items.set(row.id, skip(row, 'У должности нет названия'))
        continue
      }
      names.add(name)
      create.push(row)
      continue
    }
    claimed.add(match.id)
    let title = row.title
    if (name !== nameKey(match.title)) {
      const other = byTitle.get(name)
      if ((other && other.id !== match.id) || names.has(name)) title = match.title
    }
    names.add(nameKey(title))
    matched.push({ row, match, title })
  }

  const sourceStaff = src.filter((row) => row.kind === 'post' && row.rank < 5)
  const targetStaff = tgt.filter((row) => row.kind === 'post' && row.rank < 5)
  const movingOld = new Map(matched.filter((entry) => entry.match.kind === 'post').map((entry) => [entry.match.id, entry.row]))
  const movingNew = create.filter((row) => row.kind === 'post')
  const line = pushLine(sourceStaff, targetStaff, movingOld, movingNew)
  const current = targetStaff.map((row) => `old:${row.id}`)
  const rewrite = line.length !== current.length || line.some((slot, index) => slot !== current[index])
  const finalRank = new Map()
  if (rewrite) line.forEach((slot, index) => finalRank.set(slot, Math.max(1, STAFF_TOP - index)))
  else targetStaff.forEach((row) => finalRank.set(`old:${row.id}`, row.rank))

  for (const { row, match, title } of matched) {
    const rank = match.kind === 'post' ? (finalRank.get(`old:${match.id}`) ?? match.rank) : 0
    const added = row.rights.filter((id) => !match.rights.includes(id))
    const removed = match.rights.filter((id) => !row.rights.includes(id))
    const pagesFrom = pushPages(match.rights, match.pages)
    const pagesTo = pushPages(row.rights, row.pages)
    const pagesAdded = PAGE_IDS.filter((id) => pagesTo.has(id) && !pagesFrom.has(id))
    const pagesRemoved = PAGE_IDS.filter((id) => pagesFrom.has(id) && !pagesTo.has(id))
    const changes = []
    if (title !== match.title) changes.push('title')
    if (added.length || removed.length) changes.push('rights')
    if (pagesAdded.length || pagesRemoved.length) changes.push('pages')
    if (row.prefix !== match.prefix) changes.push('prefix')
    if (Boolean(row.accepting) !== Boolean(match.accepting)) changes.push('accepting')
    if (rank !== match.rank) changes.push('rank')
    items.set(row.id, {
      sourceId: row.id,
      targetId: match.id,
      kind: row.kind,
      title,
      titleFrom: match.title,
      state: changes.length ? 'update' : 'same',
      changes,
      added,
      removed,
      pagesAdded,
      pagesRemoved,
      prefixFrom: match.prefix,
      prefix: row.prefix,
      accepting: row.accepting,
      rankFrom: match.rank,
      rank,
    })
  }
  for (const row of create) {
    items.set(row.id, {
      sourceId: row.id,
      kind: row.kind,
      title: row.title,
      state: 'new',
      changes: [],
      prefix: row.prefix,
      accepting: row.accepting,
      rights: row.rights,
      rank: row.kind === 'post' ? (finalRank.get(`new:${row.id}`) ?? 0) : 0,
    })
  }
  const shifts = targetStaff
    .filter((row) => !movingOld.has(row.id))
    .map((row) => ({ id: row.id, title: row.title, from: row.rank, to: finalRank.get(`old:${row.id}`) ?? row.rank }))
    .filter((item) => item.from !== item.to)
  const ordered = [...chosen.map((row) => items.get(row.id)).filter(Boolean), ...gone]
  return {
    items: ordered,
    shifts,
    rewrite,
    changed: ordered.some((item) => item.state === 'new' || item.state === 'update'),
  }
}

function labelList(ids, labels, limit = 3) {
  const names = ids.map((id) => labels.get(id) || id)
  if (names.length <= limit) return names.join(', ')
  return `${names.slice(0, limit).join(', ')} и ещё ${names.length - limit}`
}

export function pushStateLabel(item) {
  if (item.state === 'new') return item.kind === 'post' ? `новая · ранг ${item.rank}` : 'новая · ранг 0'
  if (item.state === 'update') return 'обновится'
  if (item.state === 'same') return 'уже так же'
  return 'не встанет'
}

/** Что именно поменяется у совпавшей должности. Пусто — менять нечего. */
export function pushDetail(item, holders = 0) {
  if (item.state === 'skip') return [item.reason]
  if (item.state === 'new') return item.kind !== 'member' && item.prefix ? [`префикс «${item.prefix}»`] : []
  if (item.state !== 'update') return []
  const lines = []
  if (item.changes.includes('title')) lines.push(`название: «${item.titleFrom}» → «${item.title}»`)
  if (item.changes.includes('rights')) {
    const parts = []
    if (item.added.length) parts.push(`+ ${labelList(item.added, RIGHT_LABELS)}`)
    if (item.removed.length) parts.push(`− ${labelList(item.removed, RIGHT_LABELS)}`)
    lines.push(`права: ${parts.join(' · ')}`)
  }
  if (item.changes.includes('pages')) {
    const parts = []
    if (item.pagesAdded.length) parts.push(`+ ${labelList(item.pagesAdded, PAGE_LABELS)}`)
    if (item.pagesRemoved.length) parts.push(`− ${labelList(item.pagesRemoved, PAGE_LABELS)}`)
    lines.push(`вкладки: ${parts.join(' · ')}`)
  }
  if (item.changes.includes('prefix')) {
    lines.push(item.prefix ? `префикс: «${item.prefix}»` : 'префикс по названию')
  }
  if (item.changes.includes('accepting')) {
    lines.push(item.accepting ? 'заявки на должность откроются' : 'заявки на должность закроются')
  }
  if (item.changes.includes('rank')) lines.push(`ранг ${item.rankFrom} → ${item.rank}`)
  if (item.changes.includes('rights') && holders > 0) {
    lines.push(`в Telegram права обновятся у ${ruCount(holders, 'человека', 'человек', 'человек')}`)
  }
  return lines
}

export function pushShiftLine(shifts, verb = 'Сдвинутся') {
  if (!shifts?.length) return ''
  return `${verb}: ${shifts.map((item) => `${item.title} ${item.from} → ${item.to}`).join(', ')}`
}

/** Что сервер на самом деле записал в одной группе. */
export function pushReceiptLines(group) {
  if (group?.error) return [group.error]
  const lines = []
  if (group?.created?.length) {
    lines.push(`Новые: ${group.created.map((item) => `${item.title}, ранг ${item.rank}`).join('; ')}`)
  }
  if (group?.updated?.length) lines.push(`Обновлены: ${group.updated.map((item) => item.title).join(', ')}`)
  if (!lines.length) lines.push('Менять было нечего: там уже всё как здесь')
  if (group?.shifted?.length) lines.push(pushShiftLine(group.shifted, 'Сдвинулись'))
  const telegram = group?.telegram || {}
  if (telegram.synced) {
    lines.push(`В Telegram права обновлены у ${ruCount(telegram.synced, 'человека', 'человек', 'человек')}`)
  }
  if (telegram.failed) {
    const note = telegram.note ? `: ${telegram.note}` : ''
    lines.push(`У ${ruCount(telegram.failed, 'человека', 'человек', 'человек')} права в Telegram не встали${note}`)
  }
  if (group?.skipped?.length) {
    lines.push(`Не встали: ${group.skipped.map((item) => `${item.title} — ${item.reason}`).join('; ')}`)
  }
  return lines
}

/** Короткая сводка после переноса — для строки над списком должностей. */
export function pushNotice(groups) {
  const done = (groups || []).filter((group) => !group.error)
  const created = done.reduce((sum, group) => sum + (group.created?.length || 0), 0)
  const updated = done.reduce((sum, group) => sum + (group.updated?.length || 0), 0)
  const touched = done.filter((group) => (group.created?.length || 0) + (group.updated?.length || 0) > 0).length
  const parts = []
  if (touched) {
    const counts = []
    if (created) counts.push(ruCount(created, 'новая', 'новые', 'новых'))
    if (updated) counts.push(ruCount(updated, 'обновлена', 'обновлены', 'обновлено'))
    parts.push(`Перенесено в ${ruCount(touched, 'группу', 'группы', 'групп')}: ${counts.join(', ')}.`)
  }
  const failed = (groups || []).filter((group) => group.error)
  if (failed.length) parts.push(`Не обновились: ${failed.map((group) => group.title).join(', ')}.`)
  const telegram = done.reduce((sum, group) => sum + (group.telegram?.failed || 0), 0)
  if (telegram) parts.push(`У ${ruCount(telegram, 'человека', 'человек', 'человек')} права в Telegram не обновились.`)
  return parts.join(' ')
}
