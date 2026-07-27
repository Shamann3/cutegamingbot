import Dagre from '@dagrejs/dagre'

// Assigns positions left-to-right: base resources on the left, final items on the right.
export function layoutGraph(nodes, edges, opts = {}) {
  const {
    nodeWidth = 230, nodeHeight = 120,
    recipeWidth = 120, recipeHeight = 64,
    rankdir = 'LR', nodesep = 44, ranksep = 90,
  } = opts
  const sizeOf = (node) => (node.kind === 'recipe'
    ? { width: recipeWidth, height: recipeHeight }
    : { width: nodeWidth, height: nodeHeight })

  const g = new Dagre.graphlib.Graph()
  g.setGraph({ rankdir, nodesep, ranksep })
  g.setDefaultEdgeLabel(() => ({}))

  for (const node of nodes) g.setNode(node.id, sizeOf(node))
  for (const edge of edges) {
    if (g.hasNode(edge.source) && g.hasNode(edge.target)) g.setEdge(edge.source, edge.target)
  }

  Dagre.layout(g)

  const positions = {}
  for (const node of nodes) {
    const p = g.node(node.id)
    const { width, height } = sizeOf(node)
    positions[node.id] = { x: p.x - width / 2, y: p.y - height / 2 }
  }
  return positions
}
