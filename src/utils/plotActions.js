import { PlotStatus } from '../types/farm'
import { WILT_GRACE_MS } from './farmTiming'

/** Статус на экране с учётом таймеров (до следующего запроса к серверу). */
export function getEffectivePlotStatus(plot, now = Date.now()) {
  if (!plot) return plot?.status
  if (plot.status === PlotStatus.GROWING) {
    if (plot.autowaterActive) {
      if (plot.ripeAt && now >= plot.ripeAt) return PlotStatus.READY
      return PlotStatus.GROWING
    }
    if (plot.ripeAt && now >= plot.ripeAt) return PlotStatus.READY
    if (plot.wiltAt && now >= plot.wiltAt) return PlotStatus.WITHERED
    if (plot.dryAt && now >= plot.dryAt && plot.needsWater) {
      const wiltAt = plot.wiltAt ?? plot.dryAt + WILT_GRACE_MS
      if (now >= wiltAt) return PlotStatus.WITHERED
    }
  }
  return plot.status
}

export function isPlotDry(plot, now = Date.now()) {
  if (plot.status !== PlotStatus.GROWING) return false
  if (plot.autowaterActive) return false
  return Boolean(plot.needsWater) || (plot.dryAt != null && now >= plot.dryAt)
}

export function canPerformAction(plot, action, now = Date.now()) {
  if (!plot) return false
  const status = getEffectivePlotStatus(plot, now)

  switch (action) {
    case 'plant':
      return status === PlotStatus.EMPTY
    case 'water':
      return status === PlotStatus.GROWING && isPlotDry(plot, now)
    case 'autowater':
      return status === PlotStatus.GROWING && !plot.autowaterActive
    case 'harvest':
      return status === PlotStatus.READY
    case 'clear':
      return status === PlotStatus.WITHERED
    default:
      return false
  }
}
