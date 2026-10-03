import { afterEach, describe, expect, it } from 'vitest'
import { deckKey } from './useSwipeDeck'

function press(init = {}, target = document.body) {
  return {
    key: '',
    code: '',
    repeat: false,
    defaultPrevented: false,
    altKey: false,
    ctrlKey: false,
    metaKey: false,
    shiftKey: false,
    target,
    ...init,
  }
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('deckKey', () => {
  it('maps the arrows to the deck', () => {
    expect(deckKey(press({ key: 'ArrowLeft' }))).toBe('left')
    expect(deckKey(press({ key: 'ArrowRight' }))).toBe('right')
    expect(deckKey(press({ key: 'ArrowDown' }))).toBe('down')
    expect(deckKey(press({ key: 'ArrowUp' }))).toBeNull()
  })

  it('takes back with Ctrl+Z on any keyboard layout', () => {
    expect(deckKey(press({ key: 'я', code: 'KeyZ', ctrlKey: true }))).toBe('undo')
    expect(deckKey(press({ key: 'z', code: 'KeyZ', metaKey: true }))).toBe('undo')
    expect(deckKey(press({ key: 'Z', code: 'KeyZ', ctrlKey: true, shiftKey: true }))).toBeNull()
  })

  it('ignores held keys and shortcuts', () => {
    expect(deckKey(press({ key: 'ArrowRight', repeat: true }))).toBeNull()
    expect(deckKey(press({ key: 'ArrowRight', altKey: true }))).toBeNull()
    expect(deckKey(press({ key: 'ArrowRight', defaultPrevented: true }))).toBeNull()
  })

  it('leaves fields, tabs and the people list to the page', () => {
    document.body.innerHTML = '<input id="f"><div class="pay-people"><button id="p">Анна</button></div><nav class="sec-tabs"><button id="t">Нормы</button></nav>'
    expect(deckKey(press({ key: 'ArrowRight' }, document.getElementById('f')))).toBeNull()
    expect(deckKey(press({ key: 'ArrowRight' }, document.getElementById('p')))).toBeNull()
    expect(deckKey(press({ key: 'ArrowRight' }, document.getElementById('t')))).toBeNull()
  })

  it('stays quiet while a window is open on top', () => {
    document.body.innerHTML = '<div role="dialog" aria-modal="true"></div>'
    expect(deckKey(press({ key: 'ArrowRight' }))).toBeNull()
  })
})
