import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useRef } from 'react'
import { afterEach, describe, expect, it } from 'vitest'
import GroupMuteLock from './GroupMuteLock'

afterEach(() => {
  cleanup()
})

function Harness({ lock }) {
  const rootRef = useRef(null)
  return (
    <div ref={rootRef}>
      <GroupMuteLock rootRef={rootRef} lock={lock} />
      <label>
        Причина
        <input aria-label="Причина" />
      </label>
    </div>
  )
}

describe('GroupMuteLock', () => {
  it('shows the mute time and the group when a field is focused', () => {
    render(<Harness lock={{ until: '2026-10-10T18:30:00', group: 'Cute' }} />)
    fireEvent.focusIn(screen.getByLabelText('Причина'))
    expect(screen.getByRole('alertdialog').textContent).toContain('Вас замутили')
    expect(screen.getByRole('alertdialog').textContent).toContain('Cute')
    expect(screen.getByRole('alertdialog').textContent).toContain('октября')
    fireEvent.click(screen.getByRole('button', { name: 'Понятно' }))
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })

  it('stays quiet when this group has no mute', () => {
    render(<Harness lock={null} />)
    fireEvent.focusIn(screen.getByLabelText('Причина'))
    expect(screen.queryByRole('alertdialog')).toBeNull()
  })
})
