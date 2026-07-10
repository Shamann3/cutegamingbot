export function buildStrip(result, pool, opts = {}) {
  const length = opts.length ?? 40
  const resultIndex = opts.resultIndex ?? Math.max(0, length - 5)
  const fillers = (pool && pool.length) ? pool : [result]
  const cells = []
  for (let i = 0; i < length; i += 1) {
    if (i === resultIndex) {
      cells.push({ key: `r-${i}`, emoji: result.emoji, rarity: result.rarity })
    } else {
      const src = fillers[i % fillers.length]
      cells.push({ key: `c-${i}`, emoji: src.emoji, rarity: src.rarity })
    }
  }
  return { cells, resultIndex }
}

export function landingOffset(resultIndex, cellWidth, gap, viewportWidth) {
  return -(resultIndex * (cellWidth + gap) + cellWidth / 2 - viewportWidth / 2)
}

export function buildIdleStrip(pool, length = 40) {
  const cells = []
  for (let i = 0; i < length; i += 1) {
    const src = pool[i % pool.length]
    cells.push({ key: `idle-${i}`, emoji: src.emoji, rarity: src.rarity })
  }
  return { cells, resultIndex: -1 }
}
