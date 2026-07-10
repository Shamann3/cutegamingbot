import { apiRequest } from './apiClient'

export function fetchCraftRecipes() {
  return apiRequest('/api/craft/recipes')
}

export function executeCraft(slotA, slotB) {
  return apiRequest('/api/craft/execute', {
    method: 'POST',
    body: { slotA, slotB },
  })
}
