import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import GroupEnter, { cabinetNeedsGroupPick } from './GroupEnter'

describe('group enter', () => {
  afterEach(() => cleanup())

  it('asks for a group only when there are several and this is not a preview', () => {
    expect(cabinetNeedsGroupPick(2, false)).toBe(true)
    expect(cabinetNeedsGroupPick(1, false)).toBe(false)
    expect(cabinetNeedsGroupPick(3, true)).toBe(false)
  })

  it('opens the chosen group from the center list', () => {
    const onPick = vi.fn()
    render(<GroupEnter groups={[
      { chatId: -100, title: 'Игры', position: 'Модератор' },
      { chatId: -200, title: 'Новости', position: 'Администратор' },
    ]} onPick={onPick} />)
    expect(screen.getByRole('heading', { name: 'Ваши группы' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /Новости/ }))
    expect(onPick).toHaveBeenCalledWith(-200)
  })
})
