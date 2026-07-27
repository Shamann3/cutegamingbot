// Pure. No npm imports. Deterministic, order-independent, backend-valid key.
export function makeCraftKey(resultId, ingAId, ingBId) {
  const pair = [String(ingAId), String(ingBId)].sort()
  let key = `map_${resultId}_${pair[0]}_${pair[1]}`
    .toLowerCase()
    .replace(/[^a-z0-9_]/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '')
  if (!/^[a-z]/.test(key)) key = `k_${key}`
  return key.slice(0, 49)
}
