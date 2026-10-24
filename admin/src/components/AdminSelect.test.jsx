import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AdminSelect from './AdminSelect'

afterEach(() => cleanup())

describe('AdminSelect', () => {
  it('оставляет пункт нажатым и не отдаёт клик полю под списком', () => {
    const onChange = vi.fn()
    render(
      <AdminSelect
        value=""
        onChange={onChange}
        options={[
          { value: '', label: '— выберите —' },
          { value: '7', label: 'Аня · младший' },
        ]}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: '— выберите —' }))
    const option = screen.getByRole('option', { name: 'Аня · младший' })
    fireEvent.pointerDown(option)
    expect(screen.getByRole('option', { name: 'Аня · младший' })).toBeTruthy()
    fireEvent.click(option)
    expect(onChange).toHaveBeenCalledWith('7')
    expect(screen.queryByRole('option', { name: 'Аня · младший' })).toBeNull()
  })
})
