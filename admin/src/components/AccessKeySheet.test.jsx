import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AccessKeySheet from './AccessKeySheet'

afterEach(() => {
  cleanup()
})

describe('AccessKeySheet', () => {
  it('asks before access is turned off', () => {
    const onConfirm = vi.fn()
    render(
      <AccessKeySheet
        open
        name="Иван"
        kind="staff"
        step="off"
        onClose={vi.fn()}
        onConfirm={onConfirm}
      />,
    )
    expect(screen.getByRole('dialog', { name: 'Отключить доступ' })).toBeTruthy()
    expect(screen.getByText('Иван')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Отключить' }))
    expect(onConfirm).toHaveBeenCalledOnce()
  })

  it('shows the new key once and copies it', async () => {
    const writeText = vi.fn().mockResolvedValue()
    Object.assign(navigator, { clipboard: { writeText } })
    render(
      <AccessKeySheet
        open
        name="Аня"
        kind="group"
        step="shown"
        issuedKey="fresh-key"
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    )
    expect(screen.getByRole('dialog', { name: 'Ключ готов' })).toBeTruthy()
    expect(screen.getByText('fresh-key')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Скопировать' }))
    expect(writeText).toHaveBeenCalledWith('fresh-key')
    expect(await screen.findByRole('button', { name: 'Скопировано' })).toBeTruthy()
  })

  it('opens a stored key again for the creator', () => {
    render(
      <AccessKeySheet
        open
        name="Матвей"
        kind="group"
        step="look"
        issuedKey="kept-key"
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    )
    expect(screen.getByRole('dialog', { name: 'Ключ' })).toBeTruthy()
    expect(screen.getByText('kept-key')).toBeTruthy()
    expect(screen.getByText('Этот ключ сейчас действует. Его можно открыть снова.')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Выдать ключ' })).toBeNull()
  })
})
