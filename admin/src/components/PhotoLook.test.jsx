import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PhotoLook from './PhotoLook'

vi.mock('./TgPhoto', () => ({
  default: ({ alt }) => <img alt={alt} />,
  loadTgPhotoUrl: vi.fn(async () => 'blob:proof'),
}))

afterEach(() => {
  cleanup()
})

describe('PhotoLook', () => {
  it('opens the whole photo and zooms in and out', async () => {
    render(<PhotoLook fileId="proof-1" eager />)
    fireEvent.click(screen.getByRole('button', { name: 'Открыть фото целиком' }))
    expect(await screen.findByRole('dialog', { name: 'Фото доказательства' })).toBeTruthy()
    expect(screen.getByText('100%')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Ближе' }))
    expect(screen.getByText('125%')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Дальше' }))
    expect(screen.getByText('100%')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Ближе' }))
    fireEvent.click(screen.getByRole('button', { name: 'Весь кадр' }))
    expect(screen.getByText('100%')).toBeTruthy()
  })
})
