import { describe, expect, it } from 'vitest'
import { fmt, fmtCompact } from './numberFormat'

// ru-RU разделяет разряды неразрывным пробелом — сводим к обычному.
const plain = (text) => text.replace(/[\u00a0\u202f]/g, ' ')

describe('fmt', () => {
  it('разбивает разряды', () => {
    expect(plain(fmt(1234567))).toBe('1 234 567')
    expect(plain(fmt('9876'))).toBe('9 876')
    expect(fmt(0)).toBe('0')
  })

  it('пустые значения — прочерк', () => {
    expect(fmt(null)).toBe('—')
    expect(fmt(undefined)).toBe('—')
    expect(fmt('abc')).toBe('—')
  })
})

describe('fmtCompact', () => {
  it('маленькие числа как есть', () => {
    expect(fmtCompact(0)).toBe('0')
    expect(fmtCompact(999)).toBe('999')
  })

  it('тысячи, миллионы, миллиарды, триллионы', () => {
    expect(plain(fmtCompact(1500))).toBe('1,5 тыс')
    expect(plain(fmtCompact(12_345))).toBe('12,3 тыс')
    expect(plain(fmtCompact(250_000))).toBe('250 тыс')
    expect(plain(fmtCompact(2_500_000))).toBe('2,5 млн')
    expect(plain(fmtCompact(150_000_000))).toBe('150 млн')
    expect(plain(fmtCompact(3_000_000_000))).toBe('3 млрд')
    expect(plain(fmtCompact(1.2e12))).toBe('1,2 трлн')
  })

  it('на границе шага не пишет «1 000 тыс»', () => {
    expect(plain(fmtCompact(999_950))).toBe('1 млн')
    expect(plain(fmtCompact(999_999_999))).toBe('1 млрд')
    expect(plain(fmtCompact(999_400))).toBe('999 тыс')
  })

  it('отрицательные суммы', () => {
    expect(plain(fmtCompact(-2_500_000))).toMatch(/^[-−]2,5 млн$/)
  })

  it('мусор — прочерк', () => {
    expect(fmtCompact(null)).toBe('—')
    expect(fmtCompact(undefined)).toBe('—')
    expect(fmtCompact(Number.NaN)).toBe('—')
    expect(fmtCompact(Infinity)).toBe('—')
  })

  it('любая сумма до квадриллиона умещается в 10 символов', () => {
    let longest = ''
    for (let exp = 0; exp < 15; exp += 1) {
      for (const lead of [1, 1.05, 2.5, 9.99, 9.9999]) {
        const text = fmtCompact(lead * 10 ** exp)
        if (text.length > longest.length) longest = text
        expect(text.length, text).toBeLessThanOrEqual(10)
      }
    }
    expect(longest.length).toBeGreaterThan(0)
  })
})
