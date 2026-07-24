// Pure derivation of node/edge visual flags. No npm imports.

export function nodeVisual(nodeId, ctx) {
  const id = String(nodeId)
  const hidden = !ctx.visibleIds.has(id)
  let dimmed = false
  let highlighted = false
  let errored = false

  if (ctx.errorFocus && ctx.errorFocus.size > 0) {
    errored = ctx.errorFocus.has(id)
    dimmed = !errored
  } else if (ctx.selectedId && ctx.chainNodes) {
    highlighted = id === String(ctx.selectedId)
    dimmed = !ctx.chainNodes.has(id)
  } else if (ctx.matchedIds && ctx.matchedIds.size > 0) {
    highlighted = ctx.matchedIds.has(id)
    dimmed = !highlighted
  }

  return { hidden, dimmed: dimmed || hidden, highlighted, errored }
}

export function edgeVisual(edgeId, enabled, ctx) {
  const chainActive = !!(ctx.selectedId && ctx.chainEdges)
  const inChain = ctx.chainEdges ? ctx.chainEdges.has(edgeId) : false
  let opacity = enabled === false ? 0.6 : 1
  if (chainActive && !inChain) opacity = 0.12
  return { animated: inChain, opacity, dashed: enabled === false }
}
