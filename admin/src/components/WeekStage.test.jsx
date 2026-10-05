import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import WeekStage from './WeekStage'

const points = [
  { date: '2026-09-29', messages: 12 },
  { date: '2026-09-30', messages: 40 },
  { date: '2026-10-01', messages: 8 },
  { date: '2026-10-02', messages: 0 },
  { date: '2026-10-03', messages: 21 },
  { date: '2026-10-04', messages: 33 },
  { date: '2026-10-05', messages: 18 },
]

describe('WeekStage', () => {
  it('shows each day and opens that day from the column', () => {
    const onPick = vi.fn()
    render(<WeekStage points={points} active="2026-10-04" onPick={onPick} />)
    const tuesday = screen.getByRole('listitem', { name: /вт 29\.09: 12 сообщений/ })
    expect(tuesday).toBeTruthy()
    expect(screen.getByRole('listitem', { name: /вс 4\.10: 33 сообщений/ }).getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(tuesday)
    expect(onPick).toHaveBeenCalledWith(points[0])
    expect(screen.getByText('за эти дни')).toBeTruthy()
    expect(tuesday.querySelector('.week-fill').parentElement).toBeTruthy()
  })
})
