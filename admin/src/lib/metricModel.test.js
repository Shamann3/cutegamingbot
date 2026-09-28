import { describe, expect, it } from 'vitest'
import { barPercents, metricDelta, periodWhen } from './metricModel'

describe('barPercents', () => {
  it('максимум занимает всю шкалу, ноль остаётся нулём', () => {
    expect(barPercents([0, 50, 100])).toEqual([0, 50, 100])
  })

  it('отрицательные и пустые не рисуют столбец', () => {
    expect(barPercents([null, -3, 'нет', 10])).toEqual([0, 0, 0, 100])
  })

  it('все нули не делят на ноль', () => {
    expect(barPercents([0, 0])).toEqual([0, 0])
  })

  it('маленький период остаётся виден рядом с гораздо большим', () => {
    const bars = barPercents([100, 10_000])
    expect(bars[0]).toBeGreaterThanOrEqual(14)
    expect(bars[0]).toBeLessThan(bars[1])
    expect(bars[1]).toBe(100)
  })
})

describe('periodWhen', () => {
  const now = new Date(2026, 8, 29)

  it('называет день, неделю, месяц и год', () => {
    expect(periodWhen('day', now)).toBe('29 сентября 2026')
    expect(periodWhen('week', now)).toBe('28–29 сентября 2026')
    expect(periodWhen('month', now)).toBe('сентябрь 2026')
    expect(periodWhen('year', now)).toBe('2026')
  })
})

describe('metricDelta', () => {
  it('считает разницу', () => {
    expect(metricDelta(120, 100)).toBe(20)
    expect(metricDelta(80, 100)).toBe(-20)
    expect(metricDelta(5, 5)).toBe(0)
  })

  it('без чисел не выдумывает разницу', () => {
    expect(metricDelta(null, 1)).toBeNull()
    expect(metricDelta('x', 1)).toBeNull()
  })
})
