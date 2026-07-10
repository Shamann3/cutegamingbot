import { ONBOARDING_STEPS } from '../constants/onboardingSteps'

const PLANT_STEP = ONBOARDING_STEPS.findIndex((item) => item.id === 'plant')
const WATER_STEP = ONBOARDING_STEPS.findIndex((item) => item.id === 'water')
const HARVEST_STEP = ONBOARDING_STEPS.findIndex((item) => item.id === 'harvest')
const BACKPACK_STEP = ONBOARDING_STEPS.findIndex((item) => item.id === 'backpack')

export function resolveOnboardingResumeStep(onboarding, plots) {
  let step = Number(onboarding?.step ?? 0)
  if (!Number.isFinite(step) || step < 0) step = 0

  const plot = plots?.find((item) => item.id === 1)
  if (!plot) {
    return Math.min(step, ONBOARDING_STEPS.length - 1)
  }

  if (plot.status === 'GROWING') {
    step = Math.max(step, WATER_STEP)
  } else if (plot.status === 'READY') {
    step = Math.max(step, HARVEST_STEP)
  } else if (plot.status === 'EMPTY') {
    if (step >= HARVEST_STEP) {
      step = Math.max(step, BACKPACK_STEP)
    } else if (step >= WATER_STEP) {
      step = PLANT_STEP
    }
  }

  return Math.min(step, ONBOARDING_STEPS.length - 1)
}
