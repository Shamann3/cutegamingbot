import { describe, expect, it } from 'vitest'
import { PlotStatus } from '../types/farm'
import { canPerformAction, isPlotDry } from './plotActions'

describe('plotActions', () => {
  it('blocks double harvest on non-ready plot', () => {
    const plot = { id: 1, status: PlotStatus.GROWING, needsWater: false }
    expect(canPerformAction(plot, 'harvest')).toBe(false)
  })

  it('allows water when dryAt passed', () => {
    const now = 10000
    const plot = {
      id: 1,
      status: PlotStatus.GROWING,
      needsWater: false,
      dryAt: 5000,
    }
    expect(isPlotDry(plot, now)).toBe(true)
    expect(canPerformAction(plot, 'water', now)).toBe(true)
  })

  it('blocks plant on occupied plot', () => {
    const plot = { id: 1, status: PlotStatus.READY }
    expect(canPerformAction(plot, 'plant')).toBe(false)
  })
})
