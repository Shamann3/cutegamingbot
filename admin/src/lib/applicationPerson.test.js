import { describe, expect, it } from 'vitest'
import { applicationPerson } from './applicationPerson'

describe('applicationPerson', () => {
  it('shows the saved name and keeps the username beside it', () => {
    expect(applicationPerson({ name: 'Иван', username: 'ivan' })).toEqual({
      title: 'Иван',
      username: 'ivan',
    })
  })

  it('uses the staff application first name', () => {
    expect(applicationPerson({ firstName: 'Маша', username: '@masha' })).toEqual({
      title: 'Маша',
      username: 'masha',
    })
  })

  it('falls back to the username, then to a clear empty state', () => {
    expect(applicationPerson({ username: 'only' }).title).toBe('@only')
    expect(applicationPerson({ userId: 1 })).toEqual({ title: 'Имя не найдено', username: '' })
  })
})
