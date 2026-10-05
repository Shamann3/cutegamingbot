import { describe, expect, it } from 'vitest'
import { carrySpan, spanToSend, speakSpan, sumSpan } from './spanClock'

describe('span clock', () => {
  it('says the span in russian and keeps seconds', () => {
    expect(speakSpan(3600)).toBe('1 час')
    expect(speakSpan(75)).toBe('1 минута 15 секунд')
    expect(speakSpan(86400 + 5)).toBe('1 день 5 секунд')
    expect(speakSpan(21)).toBe('21 секунда')
    expect(speakSpan(11)).toBe('11 секунд')
    expect(speakSpan(0)).toBe('')
  })

  it('carries overflow and refuses a span longer than 366 days', () => {
    expect(carrySpan({ days: '0', hours: '0', minutes: '0', seconds: '75' })).toMatchObject({
      minutes: 1,
      seconds: 15,
      total: 75,
      capped: false,
    })
    expect(carrySpan({ days: '400', hours: '0', minutes: '0', seconds: '0' }).capped).toBe(true)
    expect(carrySpan({ days: '400', hours: '0', minutes: '0', seconds: '0' }).total).toBe(366 * 24 * 3600)
  })

  it('lifts a telegram-short span to 35 seconds and drops an empty one', () => {
    expect(spanToSend(10)).toBe(35)
    expect(spanToSend(35)).toBe(35)
    expect(spanToSend(90)).toBe(90)
    expect(spanToSend(0)).toBeNull()
    expect(spanToSend(sumSpan({ days: '367' }))).toBeNull()
  })
})
