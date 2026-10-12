import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ChronicleSection from './ChronicleSection'

describe('chronicle in the group cabinet', () => {
  it('opens the project story without a staff-only gate', () => {
    const { container } = render(<ChronicleSection embedded />)
    expect(screen.getByRole('heading', { name: 'История кут' })).toBeTruthy()
    expect(screen.getByRole('button', { name: /CuteChat/ })).toBeTruthy()
    expect(container.querySelector('.chs-root.is-cabinet')).toBeTruthy()
  })
})
