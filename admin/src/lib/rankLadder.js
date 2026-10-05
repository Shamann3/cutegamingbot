/** Ранги должностей администраторов. 5 и выше — создатель группы, его не переставляют. */

export const STAFF_RANK_TOP = 4

export function isOwnerPost(row) {
  return Number(row?.rank) >= 5
}

export function isFloorPost(row) {
  return row?.kind === 'member' || row?.kind === 'spamblock'
}

export function isStaffPost(row) {
  return Boolean(row) && !isOwnerPost(row) && !isFloorPost(row)
}

export function positionOrder(rows) {
  return [...(rows || [])].sort((a, b) => {
    const rank = Number(b.rank) - Number(a.rank)
    if (rank) return rank
    const ladder = Number(a.ladder || 0) - Number(b.ladder || 0)
    if (ladder) return ladder
    return Number(a.id) - Number(b.id)
  })
}

export function ladderRanks(ids) {
  const seen = new Set()
  const out = []
  for (const raw of ids || []) {
    const id = Number(raw)
    if (!id || seen.has(id)) continue
    seen.add(id)
    out.push({ id, rank: Math.max(1, STAFF_RANK_TOP - out.length), ladder: out.length })
  }
  return out
}

export function ranksDiffer(rows, ids) {
  const wanted = new Map(ladderRanks(ids).map((item) => [item.id, item.rank]))
  return (rows || []).some((row) => wanted.has(Number(row.id)) && Number(row.rank) !== wanted.get(Number(row.id)))
}
