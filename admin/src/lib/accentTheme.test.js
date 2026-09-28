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
  it('держит один оттенок и только меняет яркость', () => {
    const source = rgbToHsv(...Object.values(hexToRgb('#6BA3C9')))
    const stops = gradientStopsFrom({ hex: '#6BA3C9' })
    expect(stops).toHaveLength(4)
    stops.forEach((hex) => {
      const hsv = rgbToHsv(...Object.values(hexToRgb(hex)))
      expect(Math.abs(hsv.h - source.h)).toBeLessThan(1)
      expect(Math.abs(hsv.s - source.s)).toBeLessThan(0.02)
    })
  })

  it('белый остаётся белым на всей полосе', () => {
    const stops = gradientStopsFrom({ hex: '#ffffff' })
    stops.forEach((hex) => {
      expect(satOf(hex)).toBeLessThan(0.2)
    })
  })

  it('оставляет один цвет, даже если раньше было несколько', () => {
    const accent = normalizeAccent({
      hex: '#112233',
      stops: ['#ff0044', '#00cc88', '#2266ff', '#ffcc22', '#000000'],
    })
    expect(accent.stops).toEqual(['#ff0044'])
    expect(accent.hex).toBe('#ff0044')
    expect(gradientStopsFrom(accent)[0]).not.toBe('#00cc88')
  })

  it('чёрный остаётся чёрным и не разгорается в неон', () => {
    const stops = gradientStopsFrom({ hex: '#000000', stops: ['#000000'] })
    expect(stops.every((hex) => hex === '#000000')).toBe(true)
  })

  it('держит один свет и помнит прозрачность', () => {
    const accent = normalizeAccent({ hex: '#ffffff', scene: 'eclipse', clear: 20 })
    expect(accent.scene).toBe('horizon')
    expect(accent.clear).toBe(20)
    expect(normalizeAccent({ hex: '#ffffff', scene: 'nope', clear: 400 }).clear).toBe(100)
    expect(normalizeAccent({ hex: '#ffffff' }).scene).toBe('horizon')
  })
})
