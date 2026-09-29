import { afterEach, describe, expect, it, vi } from 'vitest'
import { releaseNestedScrolls } from './useTabScroll'

afterEach(() => {
  vi.restoreAllMocks()
})

function mockComputed() {
  vi.spyOn(window, 'getComputedStyle').mockImplementation((node) => {
    const overflow = node.style?.overflow || ''
    return {
      overflowY: overflow === 'auto' || overflow === 'scroll' ? overflow : 'visible',
      overflowX: 'visible',
      maxHeight: node.style?.maxHeight || 'none',
      height: node.style?.height || 'auto',
    }
  })
}

describe('releaseNestedScrolls', () => {
  it('убирает внутреннюю прокрутку, чтобы страница крутилась целиком', () => {
    mockComputed()
    document.body.innerHTML = '<main id="m"><section style="overflow:auto;max-height:200px"><div>список</div></section></main>'
    const main = document.getElementById('m')
    releaseNestedScrolls(main)
    const section = main.querySelector('section')
    expect(section.style.getPropertyValue('overflow')).toBe('visible')
    expect(section.style.getPropertyValue('max-height')).toBe('none')
    expect(section.style.getPropertyPriority('overflow')).toBe('important')
  })

  it('не трогает поле ввода', () => {
    mockComputed()
    document.body.innerHTML = '<main id="m"><textarea style="overflow:auto;max-height:80px"></textarea></main>'
    const main = document.getElementById('m')
    releaseNestedScrolls(main)
    const field = main.querySelector('textarea')
    expect(field.style.getPropertyValue('max-height')).toBe('80px')
  })
})
