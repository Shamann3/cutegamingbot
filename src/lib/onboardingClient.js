import { apiRequest } from './apiClient'
import * as preview from './farmPreview'

const IS_PREVIEW = import.meta.env.VITE_FARM_PREVIEW === 'true'

export function startOnboarding() {
  if (IS_PREVIEW) return preview.previewOnboardingStart()
  return apiRequest('/api/onboarding/start', { method: 'POST' })
}

export function completeOnboarding({ skipped = false } = {}) {
  if (IS_PREVIEW) return preview.previewOnboardingComplete()
  return apiRequest('/api/onboarding/complete', { method: 'POST', body: { skipped } })
}
