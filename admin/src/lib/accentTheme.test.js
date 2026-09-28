import { describe, expect, it } from 'vitest'
import { gradientStopsFrom, hexToRgb, inkOnAccent, normalizeAccent, rgbToHsv } from './accentTheme'

function satOf(hex) {
  const { r, g, b } = hexToRgb(hex)
  return rgbToHsv(r, g, b).s
}

describe('inkOnAccent', () => {
  it('кладёт тёмный текст на светлый и серый акцент', () => {
    expect(inkOnAccent('#FFFFFF')).toBe('#111111')
    expect(inkOnAccent('#C8C8C8')).toBe('#111111')
    expect(inkOnAccent('#9B8BC9')).toBe('#111111')
  })

  it('кладёт белый текст на тёмный акцент', () => {
    expect(inkOnAccent('#1A1A1A')).toBe('#ffffff')
    expect(inkOnAccent('#3A2A6A')).toBe('#ffffff')
  })
})

describe('градиент из палитры', () => {
  it('из одного цвета собирает четыре ярких', () => {
    const stops = gradientStopsFrom({ hex: '#6BA3C9' })
    expect(stops).toHaveLength(4)
    expect(satOf(stops[0])).toBeGreaterThan(0.8)
    stops.slice(1).forEach((hex) => {
      expect(satOf(hex)).toBeGreaterThan(0.8)
    })
  })

  it('белый остаётся лампой, а соседи становятся насыщенными', () => {
    const stops = gradientStopsFrom({ hex: '#ffffff' })
    expect(satOf(stops[0])).toBeLessThan(0.2)
    stops.slice(1).forEach((hex) => {
      expect(satOf(hex)).toBeGreaterThan(0.8)
    })
  })

  it('хранит до четырёх выбранных цветов и берёт первый как основной', () => {
    const accent = normalizeAccent({
      hex: '#112233',
      stops: ['#ff0044', '#00cc88', '#2266ff', '#ffcc22', '#000000'],
    })
    expect(accent.stops).toEqual(['#ff0044', '#00cc88', '#2266ff', '#ffcc22'])
    expect(accent.hex).toBe('#ff0044')
  })
})
