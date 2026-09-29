import { describe, expect, it } from 'vitest'
import { applyAccentToDocument, inkOnAccent, overlayPlateAlpha } from './accentTheme'

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

describe('overlayPlateAlpha', () => {
  it('не даёт окну стать стеклом, когда страница уже прозрачная', () => {
    expect(overlayPlateAlpha(100)).toBeCloseTo(0.82)
    expect(overlayPlateAlpha(80)).toBeCloseTo(0.82)
    expect(overlayPlateAlpha(18)).toBeCloseTo(0.82)
  })

  it('слушается ползунок, пока окно и так плотнее 35', () => {
    expect(overlayPlateAlpha(0)).toBeCloseTo(1)
    expect(overlayPlateAlpha(10)).toBeCloseTo(0.9)
  })

  it('кладёт плотность окна на документ отдельно от пластины страницы', () => {
    applyAccentToDocument({ hex: '#ffffff', h: 0, s: 0, v: 1, veil: 100, glow: 0 })
    const root = document.documentElement
    expect(root.style.getPropertyValue('--e-plate')).toBe('rgba(14, 14, 16, 0.000)')
    expect(root.style.getPropertyValue('--e-overlay')).toBe('rgba(14, 14, 16, 0.820)')
  })
})
