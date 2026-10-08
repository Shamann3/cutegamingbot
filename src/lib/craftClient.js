import { apiRequest } from './apiClient'

export function fetchCraftRecipes() {
  return apiRequest('/api/craft/recipes')
}

export function executeCraft(slotA, slotB, slotC = '') {
  return apiRequest('/api/craft/execute', {
    method: 'POST',
    body: { slotA, slotB, slotC: slotC || '' },
  })
}
