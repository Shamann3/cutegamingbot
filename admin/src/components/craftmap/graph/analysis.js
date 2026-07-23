// Pure analysis. NO external imports (must run under root vitest).

export function traverseChain(itemId, graph) {
  const start = String(itemId)
  const { edges, index } = graph
  const edgesByTarget = new Map()
  const edgesBySource = new Map()
  for (const e of edges) {
    if (!edgesByTarget.has(e.target)) edgesByTarget.set(e.target, [])
    if (!edgesBySource.has(e.source)) edgesBySource.set(e.source, [])
    edgesByTarget.get(e.target).push(e)
    edgesBySource.get(e.source).push(e)
  }

  const upstream = new Set()
  const downstream = new Set()
  const chainEdges = new Set()

  // Ancestors: walk backward (edges whose target is the current node).
  const upQueue = [start]
  const upSeen = new Set([start])
  while (upQueue.length) {
    const node = upQueue.shift()
    for (const e of edgesByTarget.get(node) || []) {
      chainEdges.add(e.id)
      if (!upSeen.has(e.source)) {
        upSeen.add(e.source)
        upstream.add(e.source)
        upQueue.push(e.source)
      }
    }
  }

  // Descendants: walk forward (edges whose source is the current node).
  const downQueue = [start]
  const downSeen = new Set([start])
  while (downQueue.length) {
    const node = downQueue.shift()
    for (const e of edgesBySource.get(node) || []) {
      chainEdges.add(e.id)
      if (!downSeen.has(e.target)) {
        downSeen.add(e.target)
        downstream.add(e.target)
        downQueue.push(e.target)
      }
    }
  }

  const nodes = new Set([start, ...upstream, ...downstream])
  return { upstream, downstream, nodes, edges: chainEdges }
}
