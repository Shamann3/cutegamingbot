import { useMemo, useState } from 'react'

export function useCraftMapState(graph) {
  const [query, setQuery] = useState('')
  const [hiddenCategories, setHidden] = useState(() => new Set())

  const categories = useMemo(() => {
    const set = new Set()
    for (const n of graph.nodes) if (n.item.sorting) set.add(n.item.sorting)
    return [...set].sort()
  }, [graph])

  const matchedIds = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return new Set()
    const out = new Set()
    for (const n of graph.nodes) {
      const i = n.item
      const hay = [i.id, i.name, i.name1, i.sorting, i.bio].filter(Boolean).join(' ').toLowerCase()
      if (hay.includes(q)) out.add(n.id)
    }
    return out
  }, [graph, query])

  const visibleIds = useMemo(() => {
    const out = new Set()
    for (const n of graph.nodes) {
      if (n.item.sorting && hiddenCategories.has(n.item.sorting)) continue
      out.add(n.id)
    }
    return out
  }, [graph, hiddenCategories])

  const toggleCategory = (cat) => {
    setHidden((prev) => {
      const next = new Set(prev)
      if (next.has(cat)) next.delete(cat)
      else next.add(cat)
      return next
    })
  }

  return { query, setQuery, categories, hiddenCategories, toggleCategory, matchedIds, visibleIds }
}
