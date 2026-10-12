import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import GroupEnter, { GroupSeal, cabinetArrival, cabinetNeedsGroupPick, entrancePace, ENTRANCE_LEAVE_MS, ENTRANCE_SEAL_MS } from './GroupEnter'

describe('group enter', () => {
  afterEach(() => cleanup())

  it('asks for a group only when there are several and this is not a preview', () => {
    expect(cabinetNeedsGroupPick(2, false)).toBe(true)
    expect(cabinetNeedsGroupPick(1, false)).toBe(false)
    expect(cabinetNeedsGroupPick(3, true)).toBe(false)
    expect(cabinetArrival(2, false)).toBe('list')
    expect(cabinetArrival(1, false)).toBe('seal')
    expect(cabinetArrival(1, true)).toBe('in')
    expect(cabinetArrival(0, false)).toBe('in')
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

  it('holds the seal a little longer and shows the role', () => {
    expect(ENTRANCE_LEAVE_MS).toBeGreaterThan(460)
    expect(ENTRANCE_SEAL_MS).toBeGreaterThan(720)
    expect(ENTRANCE_SEAL_MS).toBeLessThan(1400)
    const prev = window.matchMedia
    window.matchMedia = () => ({ matches: true, addEventListener() {}, removeEventListener() {} })
    expect(entrancePace()).toEqual({ leave: 0, seal: 0 })
    window.matchMedia = prev
    render(<GroupSeal title="Игры" position="Модератор" onEnter={() => {}} />)
    expect(screen.getByText('Игры')).toBeTruthy()
    expect(screen.getByText('Модератор')).toBeTruthy()
    expect(screen.getByText('Открываем кабинет')).toBeTruthy()
  })
})
